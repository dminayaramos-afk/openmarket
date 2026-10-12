"""Métricas de riesgo HISTÓRICAS (no son estimaciones futuras)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


def risk_metrics(close: pd.Series, periods_per_year: int = 252) -> dict:
    r = ind.log_returns(close).dropna()
    if len(r) < 30:
        return {"available": False, "reason": "Información insuficiente (menos de 30 retornos)."}
    simple = close.pct_change().dropna()
    dd = ind.drawdown(close)
    var95 = float(np.percentile(simple, 5))
    tail = simple[simple <= var95]
    ann_ret = float(np.exp(r.mean() * periods_per_year) - 1)
    vol = float(r.std(ddof=1) * np.sqrt(periods_per_year))
    return {
        "available": True,
        "basis": "histórico (no es una estimación futura)",
        "observations": len(r),
        "annualized_volatility": vol,
        "annualized_return": ann_ret,
        "return_over_vol": float(ann_ret / vol) if vol > 0 else None,
        "max_drawdown": float(dd.min()),
        "current_drawdown": float(dd.iloc[-1]),
        "var_95_1d": var95,
        "cvar_95_1d": float(tail.mean()) if len(tail) else None,
        "worst_day": float(simple.min()),
        "best_day": float(simple.max()),
        "note": "VaR/CVaR históricos al 95 % a 1 barra. Un stop-loss no garantiza ejecución al precio deseado (huecos, iliquidez).",
    }


def correlation_matrix(closes: dict[str, pd.Series], min_overlap: int = 60) -> dict:
    """Correlación de retornos diarios sobre fechas comunes (calendarios distintos reducen la muestra)."""
    frame = pd.concat({k: np.log(v / v.shift(1)) for k, v in closes.items()}, axis=1, sort=True).dropna()
    if len(frame) < min_overlap:
        return {"available": False, "overlap": len(frame),
                "reason": f"Solo {len(frame)} fechas comunes (mínimo {min_overlap})."}
    corr = frame.corr()
    return {
        "available": True, "overlap": len(frame), "symbols": list(corr.columns),
        "matrix": [[round(float(x), 3) for x in row] for row in corr.to_numpy()],
        "note": "Correlación ≠ causalidad. Calculada sobre fechas con cotización común en todos los activos.",
    }
