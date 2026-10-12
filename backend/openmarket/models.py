"""Tipos de datos compartidos."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pandas as pd

OHLCV = ["open", "high", "low", "close", "volume"]

# Estados del dato (nunca se presenta un dato sintético como real)
STATUS_SYNTHETIC = "synthetic"
STATUS_DELAYED = "delayed"
STATUS_HISTORICAL = "historical"
STATUS_LABELS = {
    STATUS_SYNTHETIC: "sintético",
    STATUS_DELAYED: "retrasado",
    STATUS_HISTORICAL: "histórico",
    "realtime": "tiempo real",
}


class DataUnavailable(Exception):
    """Ningún proveedor pudo servir datos y el modo demo está desactivado."""


class ProviderError(Exception):
    """Fallo de un proveedor concreto (red, formato, límite, símbolo desconocido)."""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Provenance:
    provider: str
    status: str
    fetched_at: str
    as_of: str | None
    currency: str
    note: str = ""
    warnings: list[str] = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        d["status_label"] = STATUS_LABELS.get(self.status, self.status)
        return d


@dataclass
class PriceSeries:
    symbol: str
    df: pd.DataFrame  # índice DatetimeIndex UTC (medianoche), columnas OHLCV
    prov: Provenance

    @property
    def is_synthetic(self) -> bool:
        return self.prov.status == STATUS_SYNTHETIC


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza: índice UTC ordenado y sin duplicados, columnas OHLCV numéricas, sin filas sin cierre."""
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    for col in OHLCV:
        if col not in out.columns:
            out[col] = float("nan") if col != "volume" else 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out[OHLCV]
    idx = pd.to_datetime(out.index, utc=True)
    out.index = idx.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["close"])
    # open/high/low ausentes -> usa el cierre (marcado como dato de solo cierre por el proveedor)
    for col in ("open", "high", "low"):
        out[col] = out[col].fillna(out["close"])
    out["high"] = out[["high", "open", "close"]].max(axis=1)
    out["low"] = out[["low", "open", "close"]].min(axis=1)
    out["volume"] = out["volume"].fillna(0.0)
    out.index.name = "date"
    return out
