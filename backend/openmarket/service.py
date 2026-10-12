"""Servicio de datos: elige proveedor, aplica caché, reintentos (en el proveedor) y respaldo sintético."""
from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .catalog import CATALOG, Asset, get_asset
from .config import Settings
from .db import Database
from .models import (
    STATUS_DELAYED,
    STATUS_HISTORICAL,
    STATUS_SYNTHETIC,
    DataUnavailable,
    PriceSeries,
    Provenance,
    clean_frame,
    utcnow_iso,
)
from .providers import synthetic
from .providers.base import Provider
from .providers.csvfile import CsvProvider
from .providers.frankfurter import FrankfurterProvider
from .providers.kraken import KrakenProvider
from .providers.stooq import StooqProvider

CACHE_TTL_SECONDS = 6 * 3600  # datos diarios: 6 h
INTERVAL = "1d"


class DataService:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.csv = CsvProvider(settings)
        self.providers: dict[str, Provider] = {
            p.name: p for p in (StooqProvider(settings), KrakenProvider(settings), FrankfurterProvider(settings))
        }
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="om-fetch")

    # --- caché --------------------------------------------------------------------------------
    def _cache_get(self, symbol: str) -> tuple[pd.DataFrame, dict, float] | None:
        with self.db.connect() as c:
            row = c.execute(
                "SELECT provider, fetched_at, payload FROM price_cache WHERE symbol=? AND interval=?",
                (symbol, INTERVAL),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        df = pd.read_json(io.StringIO(payload["frame"]), orient="split")
        df.index = pd.to_datetime(df.index, utc=True)
        return df, payload["meta"], row["fetched_at"]

    def _cache_put(self, symbol: str, provider: str, df: pd.DataFrame, meta: dict) -> None:
        payload = json.dumps({"frame": df.to_json(orient="split", date_format="iso"), "meta": meta})
        with self.db.connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO price_cache(symbol, interval, provider, fetched_at, payload) VALUES (?,?,?,?,?)",
                (symbol, INTERVAL, provider, time.time(), payload),
            )

    # --- API pública -----------------------------------------------------------------------------
    def get_series(self, symbol: str, years: int = 5, refresh: bool = False) -> PriceSeries:
        asset = get_asset(symbol)
        if asset is None:
            raise KeyError(symbol)
        errors: list[str] = []

        # 1) Archivo CSV local del usuario: datos reales sin red ni clave; tiene prioridad sobre todo lo demás
        if self.csv.has_file(asset):
            try:
                df, note = self.csv.load(asset)
                self.csv.record_ok()
                meta = {"provider": self.csv.label, "status": STATUS_HISTORICAL, "fetched_at": utcnow_iso(), "note": note}
                return PriceSeries(asset.symbol, df, _prov_from_meta(meta, asset, df))
            except Exception as exc:  # noqa: BLE001 - un CSV defectuoso no debe tumbar la app
                msg = str(exc) or type(exc).__name__
                self.csv.record_error(msg)
                errors.append(f"CSV local ignorado: {msg}")

        cached = self._cache_get(asset.symbol)

        if cached and not refresh and (time.time() - cached[2]) < CACHE_TTL_SECONDS:
            df, meta, _ = cached
            return PriceSeries(asset.symbol, df, _prov_from_meta(meta, asset, df))

        if not self.settings.offline:
            for pname in asset.providers:
                provider = self.providers.get(pname)
                if provider is None:
                    continue
                try:
                    raw, note = provider.fetch_daily(asset, years)
                    df = clean_frame(raw)
                    if df.empty:
                        raise ValueError("serie vacía tras la limpieza")
                    provider.record_ok()
                    meta = {
                        "provider": provider.label, "status": STATUS_DELAYED, "fetched_at": utcnow_iso(),
                        "note": note,
                    }
                    self._cache_put(asset.symbol, pname, df, meta)
                    return PriceSeries(asset.symbol, df, _prov_from_meta(meta, asset, df))
                except Exception as exc:  # noqa: BLE001 - cualquier fallo de proveedor se registra y se degrada
                    msg = str(exc) or type(exc).__name__
                    if "en pausa" not in msg:  # no sobrescribir la causa real con el aviso del cortacircuitos
                        provider.record_error(msg)
                    errors.append(msg)
        else:
            errors.append("modo sin conexión activado (OPENMARKET_OFFLINE)")

        # Caché caducada: mejor un dato real antiguo que uno sintético
        if cached:
            df, meta, fetched = cached
            prov = _prov_from_meta(meta, asset, df)
            age_h = (time.time() - fetched) / 3600
            prov.warnings.append(f"Caché caducada ({age_h:.0f} h): el proveedor no respondió. " + "; ".join(errors))
            return PriceSeries(asset.symbol, df, prov)

        if self.settings.demo_fallback:
            df = clean_frame(synthetic.generate(asset, years))
            prov = Provenance(
                provider="Sintético (demostración)", status=STATUS_SYNTHETIC, fetched_at=utcnow_iso(),
                as_of=_as_of(df), currency=asset.currency,
                note="DATOS GENERADOS ARTIFICIALMENTE: no son precios reales.",
                warnings=["Datos sintéticos: no use estos valores para decidir.", *errors],
            )
            return PriceSeries(asset.symbol, df, prov)
        raise DataUnavailable("; ".join(errors) or "sin proveedores disponibles")

    def get_many(self, symbols: list[str], years: int = 5) -> dict[str, PriceSeries | Exception]:
        def work(sym: str):
            try:
                return self.get_series(sym, years)
            except Exception as exc:  # noqa: BLE001
                return exc
        return dict(zip(symbols, self._pool.map(work, symbols)))

    def sources_status(self) -> list[dict]:
        enabled = not self.settings.offline
        out = [self.csv.info(True), *[p.info(enabled) for p in self.providers.values()]]
        out.append({
            "name": "synthetic", "label": "Sintético (demostración)",
            "description": "Datos generados artificialmente para probar la interfaz. Nunca son precios reales.",
            "license_note": "Sin restricciones.", "covers": list({a.category for a in CATALOG.values()}),
            "enabled": self.settings.demo_fallback, "history_note": "", "ok_count": 0, "error_count": 0,
            "last_ok": None, "last_error": None, "last_error_at": None,
        })
        return out


def _as_of(df: pd.DataFrame) -> str | None:
    return df.index[-1].isoformat() if len(df) else None


def _prov_from_meta(meta: dict, asset: Asset, df: pd.DataFrame | None = None) -> Provenance:
    return Provenance(
        provider=meta.get("provider", "?"), status=meta.get("status", STATUS_DELAYED),
        fetched_at=meta.get("fetched_at", ""), as_of=_as_of(df) if df is not None else None,
        currency=asset.currency, note=meta.get("note", ""), warnings=[],
    )
