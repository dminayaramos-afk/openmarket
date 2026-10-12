"""Históricos desde archivos CSV locales: datos reales sin red ni clave de API.

Coloca `data/prices/<SÍMBOLO>.csv` (p. ej. `AAPL.csv`, `BTC-USD.csv`, `EURUSD.csv`). Se aceptan las
exportaciones habituales (Stooq, Yahoo, etc.): separador `,` o `;`, cabeceras en inglés o español,
fechas ISO o dd/mm/aaaa y decimales con punto o coma. Solo es obligatoria la fecha y el cierre.
Si existe el archivo, tiene prioridad sobre cualquier proveedor de red.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..catalog import CATALOG, Asset
from ..config import Settings
from ..models import ProviderError, clean_frame
from .base import Provider

_ALIASES = {
    "date": ("date", "fecha", "datetime", "time", "timestamp", "day"),
    "open": ("open", "apertura", "abrir"),
    "high": ("high", "maximo", "máximo", "max"),
    "low": ("low", "minimo", "mínimo", "min"),
    "close": ("close", "cierre", "adj close", "adj_close", "adjclose", "price", "precio", "last", "último", "ultimo"),
    "volume": ("volume", "volumen", "vol", "vol."),
}
MAX_BYTES = 25 * 1024 * 1024


class CsvProvider(Provider):
    name = "csv"
    label = "Archivo CSV local"
    covers = ("stock", "etf", "crypto", "forex", "commodity", "index")
    license_note = "Tus propios datos: respeta las condiciones de la fuente de la que los descargaste."
    max_history_note = "Se lee el archivo completo; no se descarga nada."

    def __init__(self, settings: Settings):
        super().__init__()
        self.dir = Path(settings.csv_dir)

    def supports(self, asset: Asset) -> bool:
        return self.has_file(asset)

    def _path(self, asset: Asset) -> Path | None:
        # El nombre sale siempre del catálogo (nunca de la entrada del usuario): sin riesgo de path traversal
        if not self.dir.is_dir():
            return None
        wanted = asset.symbol.lower()
        for f in self.dir.iterdir():
            if f.is_file() and f.suffix.lower() == ".csv" and f.stem.lower() == wanted:
                return f
        return None

    def has_file(self, asset: Asset) -> bool:
        return self._path(asset) is not None

    def fetch_daily(self, asset: Asset, years: int) -> tuple[pd.DataFrame, str]:
        return self.load(asset)

    def load(self, asset: Asset) -> tuple[pd.DataFrame, str]:
        path = self._path(asset)
        if path is None:
            raise ProviderError(f"csv: no existe {asset.symbol}.csv en {self.dir}")
        if path.stat().st_size > MAX_BYTES:
            raise ProviderError(f"csv: {path.name} supera {MAX_BYTES // (1024 * 1024)} MB")
        df = parse_csv(path.read_text(encoding="utf-8-sig", errors="replace"), path.name)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return df, f"Archivo local {path.name} (modificado {mtime}); datos aportados por el usuario"

    def listing(self) -> list[str]:
        if not self.dir.is_dir():
            return []
        known = {s.lower(): s for s in CATALOG}
        return sorted(known[f.stem.lower()] for f in self.dir.iterdir()
                      if f.is_file() and f.suffix.lower() == ".csv" and f.stem.lower() in known)

    def info(self, enabled: bool) -> dict:
        d = super().info(enabled)
        files = self.listing()
        d["description"] = (
            f"Históricos diarios desde archivos CSV en {self.dir}. Formato: <SÍMBOLO>.csv con fecha y cierre "
            f"(open/high/low/volume opcionales). Archivos detectados: {', '.join(files) if files else 'ninguno'}."
        )
        return d


def _pick(columns: list[str], key: str) -> str | None:
    lowered = {c.strip().lower(): c for c in columns}
    for alias in _ALIASES[key]:
        if alias in lowered:
            return lowered[alias]
    return None


def parse_csv(text: str, name: str = "archivo.csv") -> pd.DataFrame:
    body = text.strip()
    if not body:
        raise ProviderError(f"csv: {name} está vacío")
    head = body.split("\n", 1)[0]
    delim = ";" if head.count(";") > head.count(",") else ("\t" if head.count("\t") > head.count(",") else ",")
    try:
        rows = list(csv.reader(io.StringIO(body), delimiter=delim))
    except csv.Error as exc:
        raise ProviderError(f"csv: {name} no se pudo leer ({exc})") from exc
    header, data = rows[0], rows[1:]
    date_col, close_col = _pick(header, "date"), _pick(header, "close")
    if date_col is None or close_col is None:
        raise ProviderError(
            f"csv: {name} necesita una columna de fecha (Date/Fecha) y otra de cierre (Close/Cierre); "
            f"cabecera encontrada: {', '.join(header)[:120]}"
        )
    raw = pd.DataFrame(data, columns=header)
    out = pd.DataFrame(index=range(len(raw)))
    out["date"] = raw[date_col].str.strip()
    for key in ("open", "high", "low", "close", "volume"):
        col = _pick(header, key)
        if col is not None:
            s = raw[col].astype(str).str.strip().str.replace(" ", "", regex=False)
            if delim == ";" or s.str.contains(r"\d,\d{1,2}$", regex=True).any():
                s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)  # 1.234,56 → 1234.56
            out[key] = pd.to_numeric(s, errors="coerce")
    dates = pd.to_datetime(out["date"], errors="coerce", utc=True, format="ISO8601")
    if dates.isna().mean() > 0.5:
        dates = pd.to_datetime(out["date"], errors="coerce", utc=True, dayfirst=True)
    out.index = dates
    out = out.drop(columns=["date"])
    out = out[out.index.notna()]
    if "close" not in out or out["close"].notna().sum() < 2:
        raise ProviderError(f"csv: {name} no contiene al menos 2 filas válidas con fecha y cierre")
    out = out.dropna(subset=["close"])  # filas sin cierre (p. ej. festivos vacíos) se descartan
    if (out["close"] <= 0).any():
        raise ProviderError(f"csv: {name} contiene cierres ≤ 0")
    return clean_frame(out)
