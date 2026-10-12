"""Frankfurter: tipos de cambio de referencia del BCE (indicativos, no ejecutables)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from ..catalog import Asset
from ..config import Settings
from ..models import ProviderError
from .base import Provider


class FrankfurterProvider(Provider):
    name = "frankfurter"
    label = "Frankfurter (BCE)"
    description = "Tipos de cambio diarios de referencia publicados por el Banco Central Europeo."
    license_note = "API abierta y gratuita. Son tipos de referencia indicativos, no precios ejecutables."
    covers = ("forex",)
    max_history_note = "Un único valor diario (sin OHLC ni volumen)."
    min_interval = 0.5

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def fetch_daily(self, asset: Asset, years: int) -> tuple[pd.DataFrame, str]:
        base, quote = asset.providers[self.name].split("/")
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=int(365.25 * years) + 7)
        resp = self.http_get(
            f"{self.settings.frankfurter_url}/{start.isoformat()}..{end.isoformat()}",
            {"base": base, "symbols": quote},
        )
        return parse_frankfurter(resp.json(), quote), f"BCE vía Frankfurter ({base}/{quote}), referencia diaria"


def parse_frankfurter(payload: dict, quote: str) -> pd.DataFrame:
    rates = (payload or {}).get("rates")
    if not isinstance(rates, dict) or not rates:
        raise ProviderError("frankfurter: respuesta sin tipos de cambio")
    rows = {k: v.get(quote) for k, v in rates.items() if isinstance(v, dict) and v.get(quote) is not None}
    if not rows:
        raise ProviderError("frankfurter: divisa no disponible")
    s = pd.Series(rows, dtype=float)
    s.index = pd.to_datetime(s.index)
    return pd.DataFrame({"close": s})  # open/high/low se rellenan con el cierre; volumen 0
