"""Motor de backtesting long-only sin información futura.

Reglas de causalidad:
- La señal de la barra t se calcula con datos ≤ t (cierre).
- La orden se ejecuta en la APERTURA de la barra t+1, con deslizamiento (slippage) y comisión.
- Los parámetros los fija el usuario ANTES de ejecutar; el motor no los optimiza.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind

STRATEGIES = {
    "buy_hold": {"label": "Comprar y mantener", "params": {}},
    "sma_cross": {"label": "Cruce de medias (SMA rápida/lenta)", "params": {"fast": 50, "slow": 200}},
    "rsi_reversion": {"label": "Reversión por RSI", "params": {"period": 14, "buy_below": 30, "sell_above": 55}},
    "breakout": {"label": "Ruptura de máximos (Donchian)", "params": {"lookback": 55}},
}


@dataclass
class Config:
    strategy: str = "sma_cross"
    params: dict | None = None
    initial_capital: float = 10_000.0
    commission_bps: float = 10.0
    slippage_bps: float = 5.0
    start: str | None = None
    end: str | None = None
    oos_fraction: float | None = None  # fracción final reservada como "fuera de muestra" (solo informe)


def target_position(df: pd.DataFrame, strategy: str, params: dict) -> pd.Series:
    """Posición deseada tras el cierre de cada barra: 1 = invertido, 0 = fuera. Causal."""
    c = df["close"]
    if strategy == "buy_hold":
        return pd.Series(1.0, index=df.index)
    if strategy == "sma_cross":
        fast, slow = int(params["fast"]), int(params["slow"])
        if fast >= slow:
            raise ValueError("fast debe ser menor que slow")
        f, s = ind.sma(c, fast), ind.sma(c, slow)
        return (f > s).astype(float).where(s.notna(), 0.0)
    if strategy == "rsi_reversion":
        r = ind.rsi(c, int(params["period"]))
        pos = np.zeros(len(c))
        holding = 0.0
        for i, v in enumerate(r.to_numpy()):
            if not np.isnan(v):
                if holding == 0.0 and v < params["buy_below"]:
                    holding = 1.0
                elif holding == 1.0 and v > params["sell_above"]:
                    holding = 0.0
            pos[i] = holding
        return pd.Series(pos, index=c.index)
    if strategy == "breakout":
        n = int(params["lookback"])
        upper = df["high"].rolling(n, min_periods=n).max().shift(1)       # máximo previo (excluye hoy)
        lower = df["low"].rolling(max(n // 2, 2), min_periods=max(n // 2, 2)).min().shift(1)
        pos = np.zeros(len(c))
        holding = 0.0
        for i in range(len(c)):
            if not np.isnan(upper.iloc[i]) and holding == 0.0 and c.iloc[i] > upper.iloc[i]:
                holding = 1.0
            elif not np.isnan(lower.iloc[i]) and holding == 1.0 and c.iloc[i] < lower.iloc[i]:
                holding = 0.0
            pos[i] = holding
        return pd.Series(pos, index=c.index)
    raise ValueError(f"estrategia desconocida: {strategy}")


def _metrics(equity: pd.Series, periods_per_year: int) -> dict:
    if len(equity) < 3:
        return {"total_return": None}
    ret = equity.pct_change().dropna()
    total = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = max(len(equity) / periods_per_year, 1e-9)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) if equity.iloc[-1] > 0 else -1.0
    vol = float(ret.std(ddof=1) * math.sqrt(periods_per_year)) if len(ret) > 2 else None
    dd = equity / equity.cummax() - 1
    sharpe = float(ret.mean() / ret.std(ddof=1) * math.sqrt(periods_per_year)) if len(ret) > 2 and ret.std(ddof=1) > 0 else None
    return {"total_return": total, "cagr": cagr, "volatility": vol, "max_drawdown": float(dd.min()), "sharpe_rf0": sharpe}


def run(df: pd.DataFrame, cfg: Config, periods_per_year: int = 252) -> dict:
    if cfg.strategy not in STRATEGIES:
        raise ValueError(f"estrategia desconocida: {cfg.strategy}")
    params = {**STRATEGIES[cfg.strategy]["params"], **(cfg.params or {})}
    data = df.copy()
    if cfg.start:
        data = data[data.index >= pd.Timestamp(cfg.start, tz="UTC")]
    if cfg.end:
        data = data[data.index <= pd.Timestamp(cfg.end, tz="UTC")]
    if len(data) < 30:
        raise ValueError("Histórico insuficiente en el periodo seleccionado (mínimo 30 barras).")
    # La señal se calcula sobre TODO el histórico previo (para que las medias estén calentadas)
    full_target = target_position(df, cfg.strategy, params)
    target = full_target.reindex(data.index)

    slip = cfg.slippage_bps / 10_000
    comm = cfg.commission_bps / 10_000
    cash, shares = float(cfg.initial_capital), 0.0
    equity, trades, open_trade = [], [], None
    pos_held = np.zeros(len(data))
    opens, closes = data["open"].to_numpy(), data["close"].to_numpy()
    tgt = target.to_numpy()
    for i in range(len(data)):
        # Ejecuta la orden decidida al cierre de la barra anterior, en la apertura de esta
        if i > 0:
            want = tgt[i - 1]
            if want == 1.0 and shares == 0.0:
                px = opens[i] * (1 + slip)
                qty = cash / (px * (1 + comm))
                fee = qty * px * comm
                cash -= qty * px + fee
                shares = qty
                open_trade = {"entry_date": data.index[i].date().isoformat(), "entry_price": px, "qty": qty, "fees": fee}
            elif want == 0.0 and shares > 0.0:
                px = opens[i] * (1 - slip)
                fee = shares * px * comm
                cash += shares * px - fee
                open_trade["fees"] += fee
                trades.append(_close_trade(open_trade, data.index[i], px, closed=True))
                shares, open_trade = 0.0, None
        pos_held[i] = 1.0 if shares > 0 else 0.0
        equity.append(cash + shares * closes[i])
    if open_trade is not None:
        trades.append(_close_trade(open_trade, data.index[-1], closes[-1], closed=False))

    eq = pd.Series(equity, index=data.index)
    bench = cfg.initial_capital * data["close"] / data["close"].iloc[0]
    n_closed = [t for t in trades if t["closed"]]
    wins = [t for t in n_closed if t["pnl"] > 0]
    result = {
        "strategy": cfg.strategy, "label": STRATEGIES[cfg.strategy]["label"], "params": params,
        "period": {"start": data.index[0].date().isoformat(), "end": data.index[-1].date().isoformat(), "bars": len(data)},
        "costs": {"commission_bps": cfg.commission_bps, "slippage_bps": cfg.slippage_bps,
                  "execution": "apertura de la barra siguiente a la señal"},
        "initial_capital": cfg.initial_capital, "final_equity": float(eq.iloc[-1]),
        "metrics": {
            **_metrics(eq, periods_per_year),
            "trades": len(trades), "win_rate": (len(wins) / len(n_closed)) if n_closed else None,
            "exposure": float(pos_held.mean()), "fees_paid": float(sum(t["fees"] for t in trades)),
        },
        "benchmark": {"label": "Comprar y mantener", **_metrics(bench, periods_per_year)},
        "trades": trades,
        "curve": {
            "dates": [d.date().isoformat() for d in data.index],
            "equity": [round(float(x), 2) for x in eq],
            "benchmark": [round(float(x), 2) for x in bench],
            "drawdown": [round(float(x), 4) for x in (eq / eq.cummax() - 1)],
        },
        "warnings": [
            "Resultado histórico simulado: no garantiza resultados futuros.",
            "Elegir la estrategia o los parámetros por haber rendido bien en este mismo periodo produce sobreajuste.",
        ],
    }
    if cfg.oos_fraction and 0.05 <= cfg.oos_fraction <= 0.8:
        cut = int(len(eq) * (1 - cfg.oos_fraction))
        result["segments"] = {
            "in_sample": _metrics(eq.iloc[:cut], periods_per_year),
            "out_of_sample": _metrics(eq.iloc[cut:], periods_per_year),
            "split_date": eq.index[cut].date().isoformat(),
            "note": "Los parámetros no se han optimizado en ningún tramo; el tramo final se muestra por separado para comprobar estabilidad.",
        }
    return result


def _close_trade(t: dict, exit_ts: pd.Timestamp, exit_price: float, closed: bool) -> dict:
    gross = (exit_price - t["entry_price"]) * t["qty"]
    pnl = gross - t["fees"]
    cost = t["entry_price"] * t["qty"]
    return {
        "entry_date": t["entry_date"], "entry_price": round(t["entry_price"], 4),
        "exit_date": exit_ts.date().isoformat(), "exit_price": round(float(exit_price), 4),
        "qty": round(t["qty"], 6), "fees": round(t["fees"], 2), "pnl": round(pnl, 2),
        "return": round(pnl / cost, 4) if cost else 0.0, "closed": closed,
        "note": None if closed else "Posición abierta valorada al último cierre",
    }
