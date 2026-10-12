"""Calculadoras de valoración (sin datos de mercado): opciones europeas (Black-Scholes-Merton) y bonos.

Son herramientas de cálculo: los resultados dependen de los parámetros que introduces. No usan precios
de mercado de opciones ni de bonos reales.
"""
from __future__ import annotations

import math


class PricingError(ValueError):
    pass


def _ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ---------------------------------------------------------------------------------------------------
# Opciones europeas
# ---------------------------------------------------------------------------------------------------
def _check_option(s: float, k: float, t: float, sigma: float | None) -> None:
    if not (s > 0 and k > 0):
        raise PricingError("El precio del subyacente y el strike deben ser positivos")
    if not (0 < t <= 50):
        raise PricingError("El plazo debe estar entre 0 y 50 años")
    if sigma is not None and not (0 < sigma <= 5):
        raise PricingError("La volatilidad debe estar entre 0 y 500 % (0 < σ ≤ 5)")


def bsm_price(s: float, k: float, t: float, r: float, sigma: float, q: float, kind: str) -> float:
    _check_option(s, k, t, sigma)
    if kind not in ("call", "put"):
        raise PricingError("El tipo debe ser 'call' o 'put'")
    sq = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / sq
    d2 = d1 - sq
    if kind == "call":
        return s * math.exp(-q * t) * _ncdf(d1) - k * math.exp(-r * t) * _ncdf(d2)
    return k * math.exp(-r * t) * _ncdf(-d2) - s * math.exp(-q * t) * _ncdf(-d1)


def bsm_greeks(s: float, k: float, t: float, r: float, sigma: float, q: float, kind: str) -> dict:
    """Griegas: delta, gamma por unidad de subyacente; vega y rho por 1 punto porcentual; theta por día natural."""
    _check_option(s, k, t, sigma)
    sq = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / sq
    d2 = d1 - sq
    eq, er = math.exp(-q * t), math.exp(-r * t)
    pdf = _npdf(d1)
    if kind == "call":
        delta = eq * _ncdf(d1)
        theta = -s * eq * pdf * sigma / (2 * math.sqrt(t)) - r * k * er * _ncdf(d2) + q * s * eq * _ncdf(d1)
        rho = k * t * er * _ncdf(d2)
    else:
        delta = eq * (_ncdf(d1) - 1.0)
        theta = -s * eq * pdf * sigma / (2 * math.sqrt(t)) + r * k * er * _ncdf(-d2) - q * s * eq * _ncdf(-d1)
        rho = -k * t * er * _ncdf(-d2)
    return {
        "delta": delta,
        "gamma": eq * pdf / (s * sq),
        "vega_per_1pct": s * eq * pdf * math.sqrt(t) / 100.0,
        "theta_per_day": theta / 365.0,
        "rho_per_1pct": rho / 100.0,
        "d1": d1, "d2": d2,
    }


def implied_vol(price: float, s: float, k: float, t: float, r: float, q: float, kind: str) -> float:
    _check_option(s, k, t, None)
    if price <= 0:
        raise PricingError("El precio de mercado de la opción debe ser positivo")
    lo, hi = 1e-6, 5.0
    p_lo, p_hi = bsm_price(s, k, t, r, lo, q, kind), bsm_price(s, k, t, r, hi, q, kind)
    if not (p_lo - 1e-9 <= price <= p_hi + 1e-9):
        raise PricingError(
            f"Precio fuera de los límites sin arbitraje: con este strike y plazo debe estar entre {p_lo:.4f} y {p_hi:.4f}"
        )
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if bsm_price(s, k, t, r, mid, q, kind) < price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------------------------------
# Bonos
# ---------------------------------------------------------------------------------------------------
def _check_bond(face: float, coupon: float, years: float, freq: int) -> int:
    if face <= 0:
        raise PricingError("El nominal debe ser positivo")
    if not (0 <= coupon <= 1):
        raise PricingError("El cupón debe estar entre 0 % y 100 %")
    if freq not in (1, 2, 4, 12):
        raise PricingError("La frecuencia debe ser 1, 2, 4 o 12 pagos al año")
    n = round(years * freq)
    if not (1 <= n <= 1200):
        raise PricingError("El plazo debe dar entre 1 y 1200 pagos")
    return n


def bond_price(face: float, coupon: float, years: float, freq: int, ytm: float) -> float:
    n = _check_bond(face, coupon, years, freq)
    y = ytm / freq
    if y <= -1:
        raise PricingError("Rendimiento no válido")
    c = face * coupon / freq
    if abs(y) < 1e-12:
        return c * n + face
    return c * (1 - (1 + y) ** -n) / y + face * (1 + y) ** -n


def bond_metrics(face: float, coupon: float, years: float, freq: int, ytm: float) -> dict:
    """Precio, duración de Macaulay y modificada (en años), convexidad y efecto de ±100 pb. Cupones a fecha de cupón (sin cupón corrido)."""
    n = _check_bond(face, coupon, years, freq)
    y = ytm / freq
    if y <= -1:
        raise PricingError("Rendimiento no válido")
    c = face * coupon / freq
    pv = [(c + (face if k == n else 0.0)) / (1 + y) ** k for k in range(1, n + 1)]
    price = sum(pv)
    mac = sum(k * v for k, v in zip(range(1, n + 1), pv, strict=True)) / price / freq
    mod = mac / (1 + y)
    conv = sum(v * k * (k + 1) for k, v in zip(range(1, n + 1), pv, strict=True)) / (price * (1 + y) ** 2) / freq ** 2
    up, down = bond_price(face, coupon, years, freq, ytm + 0.01), bond_price(face, coupon, years, freq, ytm - 0.01)
    return {
        "price": price, "price_pct_of_face": price / face * 100,
        "macaulay_duration": mac, "modified_duration": mod, "convexity": conv,
        "current_yield": (face * coupon / price) if price else None,
        "price_if_yield_up_100bp": up, "price_if_yield_down_100bp": down,
        "change_up_100bp_pct": (up / price - 1) * 100, "change_down_100bp_pct": (down / price - 1) * 100,
        "duration_approx_up_100bp_pct": -mod * 1.0 + 0.5 * conv * (0.01 ** 2) * 100,
    }


def bond_ytm(price: float, face: float, coupon: float, years: float, freq: int) -> float:
    _check_bond(face, coupon, years, freq)
    if price <= 0:
        raise PricingError("El precio debe ser positivo")
    lo, hi = -0.5, 2.0  # rendimiento anual nominal
    if not (bond_price(face, coupon, years, freq, hi) <= price <= bond_price(face, coupon, years, freq, lo)):
        raise PricingError("No existe un rendimiento entre −50 % y 200 % que dé ese precio")
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if bond_price(face, coupon, years, freq, mid) > price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)
