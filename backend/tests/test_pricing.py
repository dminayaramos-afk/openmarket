import math

import pytest

from openmarket.analysis import pricing as pr


def test_bsm_reference_values():
    # Valores de referencia clásicos: S=K=100, T=1, r=5 %, σ=20 %, q=0
    assert pr.bsm_price(100, 100, 1, 0.05, 0.2, 0, "call") == pytest.approx(10.4506, abs=1e-3)
    assert pr.bsm_price(100, 100, 1, 0.05, 0.2, 0, "put") == pytest.approx(5.5735, abs=1e-3)
    g = pr.bsm_greeks(100, 100, 1, 0.05, 0.2, 0, "call")
    assert g["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert g["gamma"] == pytest.approx(0.018762, abs=1e-5)
    assert g["vega_per_1pct"] == pytest.approx(0.37524, abs=1e-4)


@pytest.mark.parametrize("q", [0.0, 0.03])
def test_put_call_parity(q):
    s, k, t, r, sg = 120, 110, 0.75, 0.04, 0.3
    c, p = pr.bsm_price(s, k, t, r, sg, q, "call"), pr.bsm_price(s, k, t, r, sg, q, "put")
    assert c - p == pytest.approx(s * math.exp(-q * t) - k * math.exp(-r * t), abs=1e-9)


def test_greeks_match_finite_differences():
    s, k, t, r, sg, q = 100, 105, 0.5, 0.03, 0.25, 0.01
    h = 1e-3
    for kind in ("call", "put"):
        g = pr.bsm_greeks(s, k, t, r, sg, q, kind)
        dp = (pr.bsm_price(s + h, k, t, r, sg, q, kind) - pr.bsm_price(s - h, k, t, r, sg, q, kind)) / (2 * h)
        gm = (pr.bsm_price(s + h, k, t, r, sg, q, kind) - 2 * pr.bsm_price(s, k, t, r, sg, q, kind)
              + pr.bsm_price(s - h, k, t, r, sg, q, kind)) / h ** 2
        vg = (pr.bsm_price(s, k, t, r, sg + 1e-4, q, kind) - pr.bsm_price(s, k, t, r, sg - 1e-4, q, kind)) / 2e-4 / 100
        th = (pr.bsm_price(s, k, t - 1 / 365, r, sg, q, kind) - pr.bsm_price(s, k, t, r, sg, q, kind))
        assert g["delta"] == pytest.approx(dp, abs=1e-5)
        assert g["gamma"] == pytest.approx(gm, abs=1e-4)
        assert g["vega_per_1pct"] == pytest.approx(vg, abs=1e-5)
        assert g["theta_per_day"] == pytest.approx(th, abs=2e-3)


def test_implied_vol_roundtrip_and_bounds():
    price = pr.bsm_price(100, 95, 0.5, 0.02, 0.37, 0.0, "call")
    assert pr.implied_vol(price, 100, 95, 0.5, 0.02, 0.0, "call") == pytest.approx(0.37, abs=1e-6)
    with pytest.raises(pr.PricingError, match="sin arbitraje"):
        pr.implied_vol(0.0001, 100, 50, 1, 0.0, 0.0, "call")   # por debajo del valor intrínseco
    with pytest.raises(pr.PricingError):
        pr.bsm_price(-1, 100, 1, 0.01, 0.2, 0, "call")
    with pytest.raises(pr.PricingError):
        pr.bsm_price(100, 100, 1, 0.01, 0.2, 0, "straddle")


def test_bond_par_and_reference_durations():
    assert pr.bond_price(100, 0.05, 10, 1, 0.05) == pytest.approx(100.0, abs=1e-9)   # cupón = rendimiento → a la par
    m = pr.bond_metrics(100, 0.05, 10, 1, 0.05)
    assert m["macaulay_duration"] == pytest.approx(8.1078, abs=1e-3)
    assert m["modified_duration"] == pytest.approx(7.7217, abs=1e-3)


def test_bond_modified_duration_equals_numeric_derivative():
    face, cp, yrs, f, y = 1000, 0.04, 7, 2, 0.035
    p0 = pr.bond_price(face, cp, yrs, f, y)
    h = 1e-5
    numeric = -(pr.bond_price(face, cp, yrs, f, y + h) - pr.bond_price(face, cp, yrs, f, y - h)) / (2 * h) / p0
    assert pr.bond_metrics(face, cp, yrs, f, y)["modified_duration"] == pytest.approx(numeric, rel=1e-4)


def test_bond_price_falls_when_yield_rises_and_ytm_roundtrip():
    assert pr.bond_price(100, 0.05, 10, 2, 0.06) < pr.bond_price(100, 0.05, 10, 2, 0.05) < pr.bond_price(100, 0.05, 10, 2, 0.04)
    p = pr.bond_price(100, 0.03, 5, 4, 0.0425)
    assert pr.bond_ytm(p, 100, 0.03, 5, 4) == pytest.approx(0.0425, abs=1e-9)
    assert pr.bond_price(100, 0.0, 5, 1, 0.0) == pytest.approx(100.0)                # cero cupón y rendimiento 0
    with pytest.raises(pr.PricingError):
        pr.bond_ytm(1e-6, 100, 0.05, 10, 1)
    with pytest.raises(pr.PricingError):
        pr.bond_price(100, 0.05, 10, 3, 0.05)
