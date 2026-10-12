"""Indicadores técnicos (pandas/NumPy). Todas las funciones son causales: el valor en t solo usa datos ≤ t."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    """Suavizado de Wilder: semilla = media simple de las primeras n observaciones válidas; después
    out[t] = (out[t-1]·(n-1) + x[t]) / n. (ewm(adjust=False) NO es equivalente: se siembra con el primer valor.)"""
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return pd.Series(out, index=s.index)
    first = valid[0]
    seed = first + n - 1
    out[seed] = x[first:first + n].mean()
    for i in range(seed + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n if not np.isnan(x[i]) else out[i - 1]
    return pd.Series(out, index=s.index)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = wilder(gain, n)
    avg_loss = wilder(loss, n)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - 100 / (1 + rs)
    # Sin pérdidas en la ventana -> RSI 100; sin ganancias -> 0
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pct_b": (close - lower) / (upper - lower)})


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return wilder(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_s = wilder(true_range(df), n)
    plus_di = 100 * wilder(plus_dm, n) / tr_s
    minus_di = 100 * wilder(minus_dm, n) / tr_s
    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    return pd.DataFrame({"adx": wilder(dx, n), "plus_di": plus_di, "minus_di": minus_di})


def momentum(close: pd.Series, n: int = 20) -> pd.Series:
    """Variación porcentual a n periodos (ROC)."""
    return close / close.shift(n) - 1.0


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def realized_vol(close: pd.Series, n: int = 20, periods_per_year: int = 252) -> pd.Series:
    return log_returns(close).rolling(n, min_periods=n).std(ddof=1) * np.sqrt(periods_per_year)


def drawdown(close: pd.Series) -> pd.Series:
    return close / close.cummax() - 1.0


def vwap_rolling(df: pd.DataFrame, n: int = 20) -> pd.Series | None:
    """VWAP móvil con precio típico. Solo con volumen real; si no hay volumen devuelve None."""
    if float(df["volume"].sum()) <= 0:
        return None
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = (typical * df["volume"]).rolling(n, min_periods=n).sum()
    v = df["volume"].rolling(n, min_periods=n).sum().replace(0.0, np.nan)
    return pv / v


def support_resistance(df: pd.DataFrame, k: int = 5, tol: float = 0.015, max_levels: int = 3) -> dict:
    """Niveles estimados a partir de pivotes CONFIRMADOS (k velas a cada lado, sin mirar al futuro).

    Son estimaciones heurísticas, no garantías de rebote.
    """
    if len(df) < 2 * k + 5:
        return {"support": [], "resistance": []}
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    piv_hi, piv_lo = [], []
    for i in range(k, n - k):
        if highs[i] == highs[i - k:i + k + 1].max():
            piv_hi.append(highs[i])
        if lows[i] == lows[i - k:i + k + 1].min():
            piv_lo.append(lows[i])
    last = float(df["close"].iloc[-1])

    def cluster(levels: list[float]) -> list[float]:
        out: list[list[float]] = []
        for lv in sorted(levels):
            if out and abs(lv - np.mean(out[-1])) / np.mean(out[-1]) <= tol:
                out[-1].append(lv)
            else:
                out.append([lv])
        return [float(np.mean(g)) for g in out]

    levels = cluster(piv_hi + piv_lo)
    below = sorted([lv for lv in levels if lv < last], reverse=True)[:max_levels]
    above = sorted([lv for lv in levels if lv >= last])[:max_levels]
    return {"support": below, "resistance": above}


def period_returns(close: pd.Series, periods_per_year: int = 252) -> dict[str, float | None]:
    """Rendimiento por periodos (aproximación por número de barras) y desde inicio de año."""
    out: dict[str, float | None] = {}
    last = float(close.iloc[-1])
    bars = {"1S": 5, "1M": 21, "3M": 63, "6M": 126, "1A": 252}
    if periods_per_year == 365:
        bars = {"1S": 7, "1M": 30, "3M": 91, "6M": 182, "1A": 365}
    for label, n in bars.items():
        out[label] = float(last / close.iloc[-1 - n] - 1) if len(close) > n else None
    year = close.index[-1].year
    this_year = close[close.index.year == year]
    prev = close[close.index.year < year]
    if len(prev):
        out["YTD"] = float(last / prev.iloc[-1] - 1)
    elif len(this_year) > 1:
        out["YTD"] = float(last / this_year.iloc[0] - 1)
    else:
        out["YTD"] = None
    return out
