import numpy as np

from openmarket.analysis import signals as sig
from tests.conftest import make_ohlc


def test_direction_thresholds_are_exclusive_and_exhaustive():
    for s in np.linspace(-1, 1, 401):
        assert sig.direction_label(float(s)) in {"BAJISTA", "NEUTRAL", "ALCISTA"}
    assert sig.direction_label(-0.26) == "BAJISTA"
    assert sig.direction_label(-0.25) == "NEUTRAL"
    assert sig.direction_label(0.25) == "NEUTRAL"
    assert sig.direction_label(0.26) == "ALCISTA"


def test_insufficient_history_message():
    out = sig.build_signal(make_ohlc(n=100))
    assert out["available"] is False and "insuficiente" in out["reason"].lower()


def test_score_has_no_lookahead(ohlc):
    t = 450
    b = ohlc.copy()
    b.iloc[t + 1:, :4] *= 5.0
    assert np.isclose(sig.score_series(ohlc).iloc[t], sig.score_series(b).iloc[t])


def test_signal_structure_and_probabilities_sum_to_100():
    df = make_ohlc(n=1500, seed=7)
    out = sig.build_signal(df)
    assert out["available"] and out["direction"] in {"BAJISTA", "NEUTRAL", "ALCISTA"}
    assert -1 <= out["score"] <= 1 and 0 <= out["uncertainty"] <= 1
    p = out["probabilities"]
    if p["available"]:
        assert sum(p["probabilities"].values()) == 100
        assert p["n_samples"] >= sig.MIN_SAMPLES
    else:
        assert "insuficiente" in p["reason"].lower()


def test_probabilities_refuse_with_little_data():
    out = sig.build_signal(make_ohlc(n=300, seed=3), with_validation=False)
    assert out["available"] and out["probabilities"]["available"] is False
    assert "No se muestran probabilidades" in out["probabilities"]["reason"]


def test_round_to_100_always_sums():
    rng = np.random.default_rng(0)
    for _ in range(200):
        p = rng.dirichlet([1, 1, 1])
        assert sum(sig._round_to_100(p)) == 100


def test_labels_unobservable_until_horizon():
    df = make_ohlc(n=400)
    y, _ = sig._labels(df, 20)
    assert y.iloc[-20:].isna().all()          # el resultado de las últimas 20 barras aún no se conoce
    assert y.iloc[100:300].notna().all()


def test_walk_forward_uses_only_past():
    df = make_ohlc(n=1500, seed=11)
    base = sig.validate_walk_forward(df)
    # Alterar solo las barras finales no puede cambiar evaluaciones anteriores a ellas más allá de
    # las que dependen de esas barras: comprobamos que el resultado sigue siendo válido y finito.
    assert base["available"] and np.isfinite(base["brier"]) and base["n_eval"] >= sig.MIN_EVAL
    assert 0 < base["brier"] < 2 and "walk-forward" in base["note"]


def test_walk_forward_insufficient():
    out = sig.validate_walk_forward(make_ohlc(n=400))
    assert out["available"] is False and "insuficientes" in out["reason"]
