"""Stooq: CSV diario público (acciones, ETF, índices, materias primas). Datos con retraso."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pandas as pd

from ..catalog import Asset
from ..config import Settings
from ..models import ProviderError
from .base import Provider


class StooqProvider(Provider):
    name = "stooq"
    label = "Stooq"
    description = "Histórico diario (OHLCV) de acciones, ETF, índices y materias primas en CSV."
    license_note = (
        "Desde marzo de 2026 exige una clave API gratuita: solicítala en https://stooq.com/q/d/?s=spy.us&get_apikey "
        "y defínela en OPENMARKET_STOOQ_APIKEY. Revisa sus condiciones de uso antes de redistribuir datos."
    )
    covers = ("stock", "etf", "index", "commodity")
    max_history_note = "Cierres diarios; no es tiempo real."
    min_interval = 1.0

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def fetch_daily(self, asset: Asset, years: int) -> tuple[pd.DataFrame, str]:
        if not self.settings.stooq_apikey:
            raise ProviderError(KEY_HELP)
        code = asset.providers[self.name]
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=int(365.25 * years) + 7)
        params = {"s": code, "i": "d", "d1": start.strftime("%Y%m%d"), "d2": end.strftime("%Y%m%d")}
        params["apikey"] = self.settings.stooq_apikey  # nombre del parámetro NO verificado contra el servicio real
        resp = self.http_get(f"{self.settings.stooq_url}/q/d/l/", params)
        return parse_stooq_csv(resp.text), f"Stooq ({code}), cierres diarios"


KEY_HELP = (
    "stooq: requiere clave API gratuita (desde marzo de 2026). Solicítala en "
    "https://stooq.com/q/d/?s=spy.us&get_apikey y defínela en OPENMARKET_STOOQ_APIKEY"
)


def parse_stooq_csv(text: str) -> pd.DataFrame:
    body = (text or "").strip()
    if body[:200].lower().lstrip().startswith(("<!doctype", "<html")) or "get_apikey" in body[:2000].lower():
        raise ProviderError(KEY_HELP + " (el servidor devolvió una página HTML en lugar de CSV: ¿clave ausente o inválida?)")
    if not body or body.lower().startswith("no data") or "Date" not in body.split("\n", 1)[0]:
        raise ProviderError("stooq: respuesta sin datos (¿código desconocido o clave API requerida?)")
    df = pd.read_csv(io.StringIO(body))
    df.columns = [c.strip().lower() for c in df.columns]
    if "date" not in df.columns or "close" not in df.columns:
        raise ProviderError("stooq: formato CSV inesperado")
    df = df.set_index(pd.to_datetime(df["date"], errors="coerce")).drop(columns=["date"])
    df = df[df.index.notna()]
    if df.empty:
        raise ProviderError("stooq: CSV vacío")
    return df
