"""Carteras manuales y paper trading (sin dinero real, sin bróker).

Coste medio ponderado para el cálculo de rentabilidad realizada. No hay conversión de divisas: las
posiciones en una moneda distinta de la base se informan aparte y no suman al total.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .analysis.risk import risk_metrics
from .catalog import get_asset
from .db import Database
from .models import PriceSeries


class PortfolioError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class PortfolioStore:
    def __init__(self, db: Database):
        self.db = db

    # --- CRUD ------------------------------------------------------------------------------------
    def create(self, name: str, base_currency: str = "USD", paper: bool = False) -> dict:
        with self.db.connect() as c:
            cur = c.execute(
                "INSERT INTO portfolios(name, base_currency, paper, created_at) VALUES (?,?,?,?)",
                (name.strip(), base_currency.upper(), 1 if paper else 0, _now()),
            )
            return self.get(cur.lastrowid, c)

    def get(self, pid: int, conn=None) -> dict:
        def q(c):
            row = c.execute("SELECT * FROM portfolios WHERE id=?", (pid,)).fetchone()
            if not row:
                raise KeyError(pid)
            return {"id": row["id"], "name": row["name"], "base_currency": row["base_currency"],
                    "paper": bool(row["paper"]), "created_at": row["created_at"]}
        if conn is not None:
            return q(conn)
        with self.db.connect() as c:
            return q(c)

    def list(self) -> list[dict]:
        with self.db.connect() as c:
            rows = c.execute("SELECT id FROM portfolios ORDER BY id").fetchall()
            return [self.get(r["id"], c) for r in rows]

    def delete(self, pid: int) -> None:
        with self.db.connect() as c:
            c.execute("DELETE FROM portfolios WHERE id=?", (pid,))

    def transactions(self, pid: int) -> list[dict]:
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM transactions WHERE portfolio_id=? ORDER BY ts, id", (pid,)).fetchall()
        return [dict(r) for r in rows]

    # --- operaciones -----------------------------------------------------------------------------
    def add_transaction(self, pid: int, tx: dict, enforce_cash: bool = False) -> dict:
        pf = self.get(pid)
        kind = tx["type"]
        ts = tx.get("ts") or _now()
        symbol = None
        if kind in ("buy", "sell"):
            asset = get_asset(tx.get("symbol", ""))
            if asset is None:
                raise PortfolioError("Símbolo desconocido")
            symbol = asset.symbol
            if not (tx.get("quantity") and tx["quantity"] > 0 and tx.get("price") and tx["price"] > 0):
                raise PortfolioError("Cantidad y precio deben ser positivos")
        elif kind in ("deposit", "withdraw"):
            if not (tx.get("amount") and tx["amount"] > 0):
                raise PortfolioError("El importe debe ser positivo")
        state = self.positions_state(pid)
        fee = float(tx.get("fee") or 0.0)
        if fee < 0:
            raise PortfolioError("La comisión no puede ser negativa")
        if kind == "sell":
            held = state["positions"].get(symbol, {}).get("qty", 0.0)
            if tx["quantity"] > held + 1e-9:
                raise PortfolioError(f"No se puede vender más de lo que se posee ({held:g})")
        if kind == "buy" and (enforce_cash or pf["paper"]):
            cost = tx["quantity"] * tx["price"] + fee
            if cost > state["cash"] + 1e-9:
                raise PortfolioError(f"Efectivo insuficiente ({state['cash']:.2f} disponible, {cost:.2f} necesario)")
        if kind == "withdraw" and tx["amount"] > state["cash"] + 1e-9:
            raise PortfolioError("Efectivo insuficiente para retirar")
        with self.db.connect() as c:
            cur = c.execute(
                "INSERT INTO transactions(portfolio_id, ts, type, symbol, quantity, price, fee, amount, note) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (pid, ts, kind, symbol, tx.get("quantity"), tx.get("price"), fee, tx.get("amount"), (tx.get("note") or "")[:500]),
            )
            row = c.execute("SELECT * FROM transactions WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def positions_state(self, pid: int) -> dict:
        """Reproduce las transacciones: efectivo, posiciones a coste medio y P/L realizado."""
        cash = 0.0
        pos: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "avg_cost": 0.0})
        realized = 0.0
        fees = 0.0
        for t in self.transactions(pid):
            fee = t["fee"] or 0.0
            fees += fee
            if t["type"] == "deposit":
                cash += t["amount"]
            elif t["type"] == "withdraw":
                cash -= t["amount"]
            elif t["type"] == "buy":
                p = pos[t["symbol"]]
                total_cost = p["avg_cost"] * p["qty"] + t["quantity"] * t["price"] + fee
                p["qty"] += t["quantity"]
                p["avg_cost"] = total_cost / p["qty"]
                cash -= t["quantity"] * t["price"] + fee
            elif t["type"] == "sell":
                p = pos[t["symbol"]]
                realized += (t["price"] - p["avg_cost"]) * t["quantity"] - fee
                p["qty"] -= t["quantity"]
                cash += t["quantity"] * t["price"] - fee
                if p["qty"] <= 1e-12:
                    p["qty"], p["avg_cost"] = 0.0, 0.0
        return {"cash": cash, "positions": {k: v for k, v in pos.items() if v["qty"] > 0}, "realized": realized, "fees": fees}

    # --- valoración ------------------------------------------------------------------------------
    def summary(self, pid: int, series: dict[str, PriceSeries], fx=None) -> dict:
        """Valora la cartera. `fx(origen, destino) -> FxRate | None` convierte posiciones en otra moneda
        a la moneda base con el tipo de referencia más reciente; sin tipo de cambio, no se convierte (ni se inventa)."""
        pf = self.get(pid)
        st = self.positions_state(pid)
        base = pf["base_currency"]
        rows, warnings = [], []
        unconverted: dict[str, float] = defaultdict(float)  # moneda -> valor en moneda original
        fx_used: dict[str, dict] = {}
        for sym, p in st["positions"].items():
            asset = get_asset(sym)
            ps = series.get(sym)
            cur = asset.currency if asset else None
            last = float(ps.df["close"].iloc[-1]) if ps is not None else None
            native_value = last * p["qty"] if last is not None else None
            native_cost = p["avg_cost"] * p["qty"]
            rate, converted = 1.0, False
            if cur and cur != base:
                f = fx(cur, base) if fx else None
                if f is not None:
                    rate, converted = f.rate, True
                    fx_used[cur] = {"pair": f"{cur}/{base}", "rate": f.rate, "date": f.date, "source": f.source}
                else:
                    rate = None
            counted = rate is not None and native_value is not None
            value = native_value * rate if counted else None
            cost = native_cost * rate if rate is not None else None
            row = {
                "symbol": sym, "name": asset.name if asset else sym, "category": asset.category if asset else None,
                "currency": cur, "quantity": p["qty"], "avg_cost": p["avg_cost"],
                "last_price": last, "value": value, "value_native": native_value, "cost_basis": cost,
                "unrealized_pnl": ((native_value - native_cost) * rate) if counted else None,
                "unrealized_pct": ((native_value / native_cost - 1) if counted and native_cost > 0 else None),
                "data_status": ps.prov.status if ps else None, "provider": ps.prov.provider if ps else None,
                "in_base_currency": bool(counted), "converted": converted,
                "fx_rate": rate if converted else None,
            }
            if ps is not None and ps.is_synthetic:
                warnings.append(f"{sym}: valorado con datos SINTÉTICOS (no reales).")
            if rate is None and native_value is not None:
                unconverted[cur or "?"] += native_value
            rows.append(row)
        in_base = [r for r in rows if r["in_base_currency"] and r["value"] is not None]
        invested = sum(r["value"] for r in in_base)
        total = invested + st["cash"]
        for r in rows:
            r["weight"] = (r["value"] / total) if (r["in_base_currency"] and r["value"] is not None and total > 0) else None
        if fx_used:
            detail = "; ".join(f"{v['pair']} = {v['rate']:.4f} ({v['date'] or 'sin fecha'})" for v in fx_used.values())
            warnings.append(
                f"Posiciones en otras monedas convertidas a {base} con tipos de referencia del BCE, indicativos y no ejecutables: "
                f"{detail}. El P/L de esas posiciones se expresa al tipo actual: no incluye el efecto de la divisa desde la compra."
            )
        if unconverted:
            warnings.append(
                "Hay posiciones en monedas distintas de la base (" + ", ".join(sorted(unconverted)) +
                "): no se convierten a " + base + " y no suman al total porque no hay tipo de cambio disponible ahora mismo."
            )
        unreal = sum(r["unrealized_pnl"] for r in in_base if r["unrealized_pnl"] is not None)
        weights = [r["weight"] for r in rows if r["weight"]]
        hhi = float(sum(w * w for w in weights)) if weights else None
        by_cat: dict[str, float] = defaultdict(float)
        by_cur: dict[str, float] = defaultdict(float)
        for r in in_base:
            by_cat[r["category"] or "?"] += r["value"]
            by_cur[r["currency"] or base] += r["value"]
        by_cur[base] += st["cash"]
        return {
            "portfolio": pf, "cash": st["cash"], "invested_value": invested, "total_value": total,
            "realized_pnl": st["realized"], "unrealized_pnl": unreal, "fees_paid": st["fees"],
            "positions": rows, "fx_used": list(fx_used.values()),
            "allocation_by_category": {k: v / total for k, v in by_cat.items()} if total > 0 else {},
            "allocation_by_currency": {**dict(by_cur), **{f"{k} (sin convertir)": v for k, v in unconverted.items()}},
            "concentration_hhi": hhi,
            "concentration_note": "HHI: 1 = todo en un activo; valores bajos indican diversificación." if hhi else None,
            "warnings": warnings,
            "risk": self._risk(rows, series),
        }

    @staticmethod
    def _risk(rows: list[dict], series: dict[str, PriceSeries]) -> dict:
        base_rows = [r for r in rows if r["in_base_currency"] and r["value"]]
        if not base_rows:
            return {"available": False, "reason": "Sin posiciones valoradas en la moneda base."}
        closes = {r["symbol"]: series[r["symbol"]].df["close"] for r in base_rows}
        frame = pd.concat(closes, axis=1).dropna()
        if len(frame) < 60:
            return {"available": False, "reason": f"Solo {len(frame)} fechas comunes (mínimo 60)."}
        w = np.array([r["value"] for r in base_rows], dtype=float)
        w = w / w.sum()
        rets = frame.pct_change().dropna()
        port = (rets * w).sum(axis=1)
        curve = (1 + port).cumprod()
        m = risk_metrics(curve)
        m["basis"] = "pro forma: pesos actuales aplicados al histórico (no es el rendimiento real de la cartera)"
        if any(r["converted"] for r in base_rows):
            m["basis"] += "; con activos en varias monedas, no incluye el efecto de las divisas"
        m["weights_excl_cash"] = {r["symbol"]: float(x) for r, x in zip(base_rows, w)}
        return m


def paper_fill_price(last_close: float, side: str, slippage_bps: float) -> float:
    s = slippage_bps / 10_000
    return last_close * (1 + s) if side == "buy" else last_close * (1 - s)


__all__ = ["PortfolioError", "PortfolioStore", "paper_fill_price"]
