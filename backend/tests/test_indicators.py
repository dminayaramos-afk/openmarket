import numpy as np
import pandas as pd

from openmarket.analysis import indicators as ind


def test_sma_known_values():
    s = pd.Series([1.0, 2, 3, 4, 5])
    out = ind.sma(s, 3)
    assert np.isnan(out.iloc[1]) and out.iloc[2] == 2 and out.iloc[4] == 4


def test_ema_matches_recursive_definition():
    s = pd.Series([10.0, 11, 12, 11, 13, 14, 13, 15])
    n = 3
    k = 2 / (n + 1)
    expected = [s.iloc[0]]
    for v in s.iloc[1:]:
        expected.append(v * k + expected[-1] * (1 - k))
    out = ind.ema(s, n)
    assert np.allclose(out.iloc[n - 1:], expected[n - 1:])


def test_rsi_wilder_reference_series():
    # Serie de referencia clásica (Wilder / StockCharts): RSI(14) de la primera ventana ≈ 70.46
    close = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                       45.89, 46.03, 45.61, 46.28, 46.28])
    assert abs(ind.rsi(close, 14).iloc[-1] - 70.46) < 0.1


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1.0, 60))
    assert ind.rsi(up, 14).iloc[-1] == 100.0
    down = pd.Series(np.arange(60.0, 1, -1))
    assert ind.rsi(down, 14).iloc[-1] == 0.0


def test_bollinger_width_and_macd_identity(ohlc):
    c = ohlc["close"]
    bb = ind.bollinger(c)
    valid = bb.dropna()
    assert (valid["upper"] >= valid["mid"]).all() and (valid["mid"] >= valid["lower"]).all()
    m = ind.macd(c).dropna()
    assert np.allclose(m["hist"], m["macd"] - m["signal"])


def test_atr_adx_positive(ohlc):
    assert (ind.atr(ohlc).dropna() > 0).all()
    a = ind.adx(ohlc)["adx"].dropna()
    assert ((a >= 0) & (a <= 100)).all()


def test_drawdown_range(ohlc):
    dd = ind.drawdown(ohlc["close"])
    assert dd.max() <= 0 and dd.min() > -1


def test_indicators_are_causal(ohlc):
    """El valor en t no cambia si se modifican barras futuras."""
    t = 400
    a = ohlc.copy()
    b = ohlc.copy()
    b.iloc[t + 1:, :4] *= 3.0
    for fn in (lambda d: ind.sma(d["close"], 50), lambda d: ind.rsi(d["close"]), lambda d: ind.atr(d),
               lambda d: ind.macd(d["close"])["hist"], lambda d: ind.adx(d)["adx"]):
        assert np.isclose(fn(a).iloc[t], fn(b).iloc[t])


def test_support_resistance_levels_straddle_price(ohlc):
    lv = ind.support_resistance(ohlc)
    last = ohlc["close"].iloc[-1]
    assert all(x < last for x in lv["support"]) and all(x >= last for x in lv["resistance"])


def test_period_returns(ohlc):
    r = ind.period_returns(ohlc["close"])
    c = ohlc["close"]
    assert np.isclose(r["1M"], c.iloc[-1] / c.iloc[-22] - 1)
    assert r["YTD"] is not None
