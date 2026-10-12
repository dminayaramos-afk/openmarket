"""Kraken: velas OHLC diarias públicas de mercados spot (un único exchange)."""
from __future__ import annotations

import pandas as pd

from ..catalog import Asset
from ..config import Settings
from ..models import ProviderError
from .base import Provider


class KrakenProvider(Provider):
    name = "kraken"
    label = "Kraken (spot)"
    description = "Velas diarias OHLCV de pares spot de Kraken mediante su API pública."
    license_note = "API pública sin clave. Refleja solo el libro de Kraken; otros exchanges pueden cotizar distinto."
    covers = ("crypto",)
    max_history_note = "La API pública devuelve como máximo ~720 velas diarias (≈2 años)."
    min_interval = 1.0

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def fetch_daily(self, asset: Asset, years: int) -> tuple[pd.DataFrame, str]:
        pair = asset.providers[self.name]
        resp = self.http_get(f"{self.settings.kraken_url}/0/public/OHLC", {"pair": pair, "interval": 1440})
        return parse_kraken(resp.json()), f"Kraken spot ({pair}), velas diarias; la última vela puede estar incompleta"


def parse_kraken(payload: dict) -> pd.DataFrame:
    if not isinstance(payload, dict):
        raise ProviderError("kraken: respuesta inválida")
    if payload.get("error"):
        raise ProviderError(f"kraken: {payload['error'][0] if payload['error'] else 'error'}")
    result = payload.get("result") or {}
    keys = [k for k in result if k != "last"]
    if not keys or not result[keys[0]]:
        raise ProviderError("kraken: sin velas")
    rows = result[keys[0]]
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df.index = pd.to_datetime(pd.to_numeric(df["time"]), unit="s", utc=True)
    return df[["open", "high", "low", "close", "volume"]]
