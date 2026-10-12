"""Generador de datos SINTÉTICOS deterministas para probar la interfaz sin conexión.

Nunca representan precios reales: la procedencia siempre los marca como 'synthetic'.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from ..catalog import Asset

_BASE_PRICE = {"stock": 120.0, "etf": 150.0, "crypto": 30000.0, "forex": 1.1, "commodity": 80.0, "index": 8000.0}
_VOL = {"stock": 0.28, "etf": 0.16, "crypto": 0.70, "forex": 0.07, "commodity": 0.25, "index": 0.17}
_DRIFT = {"stock": 0.08, "etf": 0.07, "crypto": 0.15, "forex": 0.0, "commodity": 0.03, "index": 0.07}


def generate(asset: Asset, years: int = 5, end: pd.Timestamp | None = None) -> pd.DataFrame:
    seed = int(hashlib.sha256(asset.symbol.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    end = (end or pd.Timestamp.now(tz="UTC")).normalize()
    freq = "D" if asset.category == "crypto" else "B"
    n = int(years * (365 if freq == "D" else 252))
    idx = pd.date_range(end=end, periods=n, freq=freq, tz="UTC")
    vol, drift = _VOL.get(asset.category, 0.2), _DRIFT.get(asset.category, 0.05)
    ppy = 365 if freq == "D" else 252
    # Volatilidad con regímenes suaves para que los indicadores muestren algo de estructura
    regime = 1 + 0.6 * np.sin(np.linspace(0, 6 * np.pi, n) + rng.uniform(0, 6.28))
    daily = rng.normal(drift / ppy, vol / np.sqrt(ppy) * regime.clip(0.4))
    close = (_BASE_PRICE.get(asset.category, 100.0) * (0.6 + (seed % 100) / 100)) * np.exp(np.cumsum(daily))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, vol / np.sqrt(ppy) * 0.15, n))
    spread = np.abs(rng.normal(0, vol / np.sqrt(ppy) * 0.6, n))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = (rng.lognormal(mean=13, sigma=0.4, size=n)).round()
    if asset.category in ("forex", "index"):
        volume = np.zeros(n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
