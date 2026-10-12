"""Señales BAJISTA / NEUTRAL / ALCISTA, probabilidades empíricas y validación walk-forward.

Principios:
- La *puntuación técnica* (score ∈ [-1, 1]) NO es una probabilidad.
- Las *probabilidades* son frecuencias históricas empíricas del propio activo, condicionadas al mismo
  estado de señal, calculadas solo con información disponible en cada momento (sin fuga del futuro).
  Se muestran únicamente si hay muestra suficiente; si no, se informa de la insuficiencia.
- Un backtest de las probabilidades (walk-forward) mide si superan a la frecuencia incondicional
  (Brier score / log loss). Con solapamiento de ventanas, la muestra efectiva es mucho menor que n.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind

# Umbrales EXCLUYENTES y exhaustivos de la dirección según el score:
#   score <  -THRESH  -> BAJISTA | -THRESH <= score <= +THRESH -> NEUTRAL | score > +THRESH -> ALCISTA
THRESH = 0.25
MIN_BARS = 220            # histórico mínimo para calcular la señal (SMA200 + margen)
MIN_SAMPLES = 100         # observaciones condicionadas mínimas para mostrar probabilidades
MIN_EVAL = 30             # evaluaciones mínimas para validar el modelo
HORIZON = 20              # barras (≈ 1 mes bursátil)
CLASS_NAMES = ("bajada", "neutral", "subida")  # índices 0, 1, 2


def direction_label(score: float) -> str:
    if score < -THRESH:
        return "BAJISTA"
    if score > THRESH:
        return "ALCISTA"
    return "NEUTRAL"


def state_series(score: pd.Series) -> pd.Series:
    """-1 / 0 / +1 (NaN si no hay score)."""
    st = pd.Series(np.where(score > THRESH, 1.0, np.where(score < -THRESH, -1.0, 0.0)), index=score.index)
    return st.where(score.notna())


def components(df: pd.DataFrame) -> pd.DataFrame:
    """Componentes de la puntuación, cada uno en [-1, 1], todos causales."""
    c = df["close"]
    s50, s200 = ind.sma(c, 50), ind.sma(c, 200)
    trend = (((c > s50).astype(float) + (c > s200).astype(float) + (s50 > s200).astype(float)) / 3 * 2 - 1)
    trend = trend.where(s200.notna())
    daily_vol = ind.log_returns(c).rolling(63, min_periods=30).std()
    roc = ind.momentum(c, 20)
    mom = (roc / (2 * daily_vol * np.sqrt(20))).clip(-1, 1)
    m = ind.macd(c)
    a = ind.atr(df, 14)
    macd_c = np.tanh(m["hist"] / a.replace(0, np.nan))
    r = ind.rsi(c, 14)
    rsi_c = ((r - 50) / 25).clip(-1, 1)
    return pd.DataFrame({"tendencia": trend, "momentum": mom, "macd": macd_c, "rsi": rsi_c})


COMPONENT_LABELS = {
    "tendencia": "Tendencia (precio vs SMA50/SMA200 y cruce de medias)",
    "momentum": "Momentum a 20 barras (normalizado por volatilidad)",
    "macd": "Histograma MACD (normalizado por ATR)",
    "rsi": "RSI(14) respecto a 50",
}


def score_series(df: pd.DataFrame) -> pd.Series:
    comp = components(df)
    return comp.mean(axis=1, skipna=False)  # NaN si falta algún componente


def _labels(df: pd.DataFrame, h: int) -> tuple[pd.Series, pd.Series]:
    """Etiqueta de resultado a h barras: 0 bajada, 1 neutral, 2 subida (NaN si aún no es observable).

    Umbral del resultado: ±0.5·σ_t·√h con σ_t = desviación de retornos logarítmicos diarios (63 barras)
    conocida en t. El resultado de t se conoce en t+h; nunca se usa antes.
    """
    c = df["close"]
    fwd = np.log(c.shift(-h) / c)
    sigma = ind.log_returns(c).rolling(63, min_periods=30).std()
    theta = 0.5 * sigma * np.sqrt(h)
    y = pd.Series(np.where(fwd > theta, 2.0, np.where(fwd < -theta, 0.0, 1.0)), index=c.index)
    y = y.where(fwd.notna() & theta.notna())
    return y, fwd


def _round_to_100(probs: np.ndarray) -> list[int]:
    """Redondeo por mayor resto para que sumen exactamente 100."""
    raw = probs * 100
    floor = np.floor(raw).astype(int)
    rem = 100 - floor.sum()
    order = np.argsort(-(raw - floor))
    for i in range(rem):
        floor[order[i % len(floor)]] += 1
    return [int(x) for x in floor]


def _conditional_probs(y: np.ndarray, st: np.ndarray, t: int, h: int, state: float) -> tuple[np.ndarray | None, int]:
    """Probabilidades en el instante t usando solo observaciones con t' + h <= t y mismo estado."""
    hi = t - h + 1  # t' en [0, t-h]
    if hi <= 0:
        return None, 0
    mask = (st[:hi] == state) & ~np.isnan(y[:hi])
    n = int(mask.sum())
    if n < MIN_SAMPLES:
        return None, n
    counts = np.array([(y[:hi][mask] == k).sum() for k in (0.0, 1.0, 2.0)], dtype=float)
    probs = (counts + 1.0) / (counts.sum() + 3.0)  # suavizado de Laplace
    return probs, n


def estimate_probabilities(df: pd.DataFrame, horizon: int = HORIZON) -> dict:
    score = score_series(df)
    st = state_series(score)
    y, _ = _labels(df, horizon)
    t = len(df) - 1
    if np.isnan(st.iloc[-1]):
        return {"available": False, "reason": "Histórico insuficiente para calcular el estado de la señal."}
    probs, n = _conditional_probs(y.to_numpy(), st.to_numpy(), t, horizon, st.iloc[-1])
    if probs is None:
        return {
            "available": False, "n_samples": n, "min_samples": MIN_SAMPLES,
            "reason": f"Información insuficiente: {n} observaciones comparables (mínimo {MIN_SAMPLES}). "
                      "No se muestran probabilidades.",
        }
    pct = _round_to_100(probs)
    return {
        "available": True, "horizon_bars": horizon, "n_samples": n,
        "effective_samples": round(n / horizon, 1),
        "probabilities": {"bajada": pct[0], "neutral": pct[1], "subida": pct[2]},
        "definition": (
            f"Bajada: retorno a {horizon} barras < −0,5·σ·√{horizon}; subida: > +0,5·σ·√{horizon}; "
            "neutral: el resto (σ = volatilidad diaria de las últimas 63 barras)."
        ),
        "method": "Frecuencias históricas empíricas de este activo con el mismo estado de señal "
                  "(suavizado de Laplace). No es una predicción ni un modelo calibrado de forma independiente.",
        "caveat": f"Las ventanas de {horizon} barras se solapan: la muestra efectiva es ≈ n/{horizon}.",
    }


def validate_walk_forward(df: pd.DataFrame, horizon: int = HORIZON, step: int = 5) -> dict:
    """Valida las probabilidades: en cada t usa solo el pasado y compara con el resultado real a t+h."""
    score = score_series(df)
    st = state_series(score).to_numpy()
    y = _labels(df, horizon)[0].to_numpy()
    n = len(df)
    briers, base_briers, logs, base_logs = [], [], [], []
    start = max(MIN_BARS + MIN_SAMPLES // 2, 250)
    for t in range(start, n - horizon, step):
        if np.isnan(st[t]) or np.isnan(y[t]):
            continue
        probs, _ = _conditional_probs(y, st, t, horizon, st[t])
        if probs is None:
            continue
        hi = t - horizon + 1
        valid = y[:hi][~np.isnan(y[:hi])]
        if len(valid) < MIN_SAMPLES:
            continue
        base = (np.array([(valid == k).sum() for k in (0.0, 1.0, 2.0)]) + 1.0)
        base = base / base.sum()
        onehot = np.zeros(3)
        onehot[int(y[t])] = 1.0
        briers.append(float(((probs - onehot) ** 2).sum()))
        base_briers.append(float(((base - onehot) ** 2).sum()))
        logs.append(float(-np.log(probs[int(y[t])])))
        base_logs.append(float(-np.log(base[int(y[t])])))
    if len(briers) < MIN_EVAL:
        return {
            "available": False, "n_eval": len(briers),
            "reason": f"Evaluaciones insuficientes ({len(briers)}; mínimo {MIN_EVAL}). Se necesita más histórico "
                      "para validar las probabilidades fuera de muestra.",
        }
    b, bb = float(np.mean(briers)), float(np.mean(base_briers))
    skill = 1 - b / bb if bb > 0 else 0.0
    return {
        "available": True, "n_eval": len(briers), "brier": round(b, 4), "brier_baseline": round(bb, 4),
        "log_loss": round(float(np.mean(logs)), 4), "log_loss_baseline": round(float(np.mean(base_logs)), 4),
        "skill_vs_baseline": round(skill, 4),
        "verdict": ("Supera marginalmente a la frecuencia incondicional" if skill > 0.01
                    else "NO supera a la frecuencia incondicional: las probabilidades condicionadas no aportan información fiable"),
        "note": "Evaluación fuera de muestra con ventana creciente (walk-forward). Resultados pasados no garantizan resultados futuros.",
    }


def build_signal(df: pd.DataFrame, horizon: int = HORIZON, with_validation: bool = True) -> dict:
    """Resultado completo y explicable para la ficha del activo."""
    if len(df) < MIN_BARS:
        return {
            "available": False,
            "reason": f"Información insuficiente: {len(df)} barras disponibles (mínimo {MIN_BARS}).",
        }
    comp = components(df)
    last = comp.iloc[-1]
    if last.isna().any():
        return {"available": False, "reason": "Información insuficiente para calcular todos los componentes."}
    score = float(last.mean())
    label = direction_label(score)
    close = df["close"]

    # Incertidumbre: desacuerdo entre componentes + percentil de volatilidad actual
    disagreement = float(min(1.0, last.std(ddof=0) / 0.6))
    vol20 = ind.realized_vol(close, 20)
    vol_hist = vol20.dropna()
    vol_pct = float((vol_hist <= vol_hist.iloc[-1]).mean()) if len(vol_hist) > 30 else 0.5
    unc = round(0.5 * disagreement + 0.5 * vol_pct, 2)
    unc_label = "alta" if unc >= 0.66 else "media" if unc >= 0.4 else "baja"

    favorable, unfavorable = [], []
    for k, v in last.items():
        text = f"{COMPONENT_LABELS[k]}: {v:+.2f}"
        if v > 0.1:
            favorable.append(text)
        elif v < -0.1:
            unfavorable.append(text)
    rsi_now = float(ind.rsi(close, 14).iloc[-1])
    risks = []
    if rsi_now >= 70:
        risks.append(f"RSI en sobrecompra ({rsi_now:.0f}): riesgo de corrección o consolidación.")
    if rsi_now <= 30:
        risks.append(f"RSI en sobreventa ({rsi_now:.0f}): puede persistir la debilidad.")
    if vol_pct >= 0.8:
        risks.append("Volatilidad actual en el 20 % superior de su historia.")
    dd = float(ind.drawdown(close).iloc[-1])
    if dd <= -0.2:
        risks.append(f"Precio un {abs(dd) * 100:.0f} % por debajo de su máximo histórico en la muestra.")

    explanation = (
        f"La puntuación técnica es {score:+.2f} (de −1 a +1) → {label}. "
        f"Es una combinación equiponderada de 4 componentes de tendencia y momentum; no es una probabilidad. "
        f"Incertidumbre {unc_label} ({unc:.2f}) por el desacuerdo entre componentes y el nivel de volatilidad."
    )
    out = {
        "available": True,
        "direction": label,
        "score": round(score, 3),
        "intensity": round(abs(score), 3),
        "thresholds": {"bajista": f"score < −{THRESH}", "neutral": f"−{THRESH} ≤ score ≤ +{THRESH}", "alcista": f"score > +{THRESH}"},
        "horizon_bars": horizon,
        "horizon_text": f"≈ {horizon} barras diarias",
        "uncertainty": unc, "uncertainty_label": unc_label,
        "components": {k: round(float(v), 3) for k, v in last.items()},
        "favorable": favorable, "unfavorable": unfavorable, "risks": risks,
        "data_used": f"{len(df)} cierres diarios hasta {df.index[-1].date().isoformat()}",
        "computed_at": pd.Timestamp.now(tz="UTC").replace(microsecond=0).isoformat(),
        "explanation": explanation,
        "probabilities": estimate_probabilities(df, horizon),
        "disclaimer": "Análisis cuantitativo informativo. No es asesoramiento financiero ni una predicción.",
    }
    if with_validation:
        out["validation"] = validate_walk_forward(df, horizon)
    return out
