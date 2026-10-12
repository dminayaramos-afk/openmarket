import numpy as np
import pandas as pd
import pytest

from openmarket.analysis import backtest as bt
from tests.conftest import make_ohlc


def test_buy_hold_without_costs_matches_price(ohlc):
    res = bt.run(ohlc, bt.Config(strategy="buy_hold", commission_bps=0, slippage_bps=0))
    # Entra en la apertura de la 2.ª barra (señal en la 1.ª) -> equity final = capital * close_fin / open_2
    expected = 10_000 * ohlc["close"].iloc[-1] / ohlc["open"].iloc[1]
    assert np.isclose(res["final_equity"], expected, rtol=1e-6)


def test_costs_reduce_returns(ohlc):
    free = bt.run(ohlc, bt.Config(strategy="sma_cross", params={"fast": 20, "slow": 60}, commission_bps=0, slippage_bps=0))
    paid = bt.run(ohlc, bt.Config(strategy="sma_cross", params={"fast": 20, "slow": 60}, commission_bps=25, slippage_bps=25))
    assert paid["final_equity"] < free["final_equity"] and paid["metrics"]["fees_paid"] > 0


def test_signal_executes_next_bar_not_same_bar(ohlc):
    res = bt.run(ohlc, bt.Config(strategy="sma_cross", params={"fast": 20, "slow": 60}, commission_bps=0, slippage_bps=0))
    tgt = bt.target_position(ohlc, "sma_cross", {"fast": 20, "slow": 60})
    first_signal = tgt[tgt == 1.0].index[0]
    entry = pd.Timestamp(res["trades"][0]["entry_date"], tz="UTC")
    assert entry > first_signal
    pos = ohlc.index.get_loc(first_signal)
    assert entry == ohlc.index[pos + 1]


def test_no_lookahead_changing_future_does_not_change_past(ohlc):
    cut = 450
    a = ohlc.copy()
    b = ohlc.copy()
    b.iloc[cut + 1:, :4] *= 0.2
    ra = bt.run(a, bt.Config(strategy="sma_cross", params={"fast": 20, "slow": 60}))
    rb = bt.run(b, bt.Config(strategy="sma_cross", params={"fast": 20, "slow": 60}))
    ea = dict(zip(ra["curve"]["dates"], ra["curve"]["equity"]))
    eb = dict(zip(rb["curve"]["dates"], rb["curve"]["equity"]))
    d = ohlc.index[cut].date().isoformat()
    assert ea[d] == eb[d]


@pytest.mark.parametrize("strategy", ["buy_hold", "sma_cross", "rsi_reversion", "breakout"])
def test_all_strategies_run_and_report(strategy, ohlc):
    res = bt.run(ohlc, bt.Config(strategy=strategy, oos_fraction=0.3))
    assert res["metrics"]["max_drawdown"] <= 0
    assert len(res["curve"]["equity"]) == len(res["curve"]["benchmark"]) == res["period"]["bars"]
    assert "segments" in res and res["segments"]["out_of_sample"]["total_return"] is not None
    assert any("sobreajuste" in w for w in res["warnings"])


def test_invalid_params_and_short_history():
    with pytest.raises(ValueError):
        bt.run(make_ohlc(), bt.Config(strategy="sma_cross", params={"fast": 100, "slow": 50}))
    with pytest.raises(ValueError):
        bt.run(make_ohlc(n=20), bt.Config(strategy="buy_hold"))
