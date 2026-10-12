"""Alertas locales: se evalúan cuando la aplicación está abierta (no hay servicio en segundo plano).

Tipos: precio por encima/debajo, RSI(14) por encima/debajo y variación diaria por encima/debajo.
Una alerta se dispara una sola vez y se puede rearmar. Sin datos reales no se evalúa con datos sintéticos.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .analysis import indicators as ind
from .catalog import get_asset
from .db import Database

KINDS = {
    "price_above": "Precio por encima de",
    "price_below": "Precio por debajo de",
    "rsi_above": "RSI(14) por encima de",
    "rsi_below": "RSI(14) por debajo de",
    "change_above": "Variación diaria (%) por encima de",
    "change_below": "Variación diaria (%) por debajo de",
}


class AlertError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row(r) -> dict:
    d = dict(r)
    d["active"] = bool(d["active"])
    d["kind_label"] = KINDS.get(d["kind"], d["kind"])
    return d


class AlertStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, symbol: str, kind: str, threshold: float, note: str = "") -> dict:
        asset = get_asset(symbol)
        if asset is None:
            raise AlertError("Símbolo desconocido")
        if kind not in KINDS:
            raise AlertError("Tipo de alerta no válido")
        if kind.startswith("rsi") and not (0 <= threshold <= 100):
            raise AlertError("El RSI debe estar entre 0 y 100")
        if kind.startswith("price") and threshold <= 0:
            raise AlertError("El precio debe ser positivo")
        with self.db.connect() as c:
            cur = c.execute("INSERT INTO alerts(symbol, kind, threshold, note, created_at) VALUES (?,?,?,?,?)",
                            (asset.symbol, kind, threshold, note[:200], _now()))
            return _row(c.execute("SELECT * FROM alerts WHERE id=?", (cur.lastrowid,)).fetchone())

    def list(self) -> list[dict]:
        with self.db.connect() as c:
            return [_row(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC").fetchall()]

    def delete(self, aid: int) -> bool:
        with self.db.connect() as c:
            return c.execute("DELETE FROM alerts WHERE id=?", (aid,)).rowcount > 0

    def rearm(self, aid: int) -> bool:
        with self.db.connect() as c:
            return c.execute("UPDATE alerts SET active=1, triggered_at=NULL WHERE id=?", (aid,)).rowcount > 0

    def evaluate(self, service) -> dict:
        """Evalúa las alertas activas. Devuelve las disparadas ahora y los avisos (símbolos sin datos reales)."""
        triggered, skipped = [], []
        active = [a for a in self.list() if a["active"]]
        cache: dict[str, dict] = {}
        for a in active:
            sym = a["symbol"]
            if sym not in cache:
                cache[sym] = self._snapshot(service, sym)
            snap = cache[sym]
            if snap.get("error"):
                skipped.append({"id": a["id"], "symbol": sym, "reason": snap["error"]})
                continue
            value = {"price": snap["price"], "rsi": snap["rsi"], "change": snap["change_pct"]}[a["kind"].split("_")[0]]
            if value is None:
                skipped.append({"id": a["id"], "symbol": sym, "reason": "valor no disponible"})
                continue
            hit = value > a["threshold"] if a["kind"].endswith("above") else value < a["threshold"]
            with self.db.connect() as c:
                if hit:
                    c.execute("UPDATE alerts SET active=0, triggered_at=?, last_value=?, last_source=? WHERE id=?",
                              (_now(), value, snap["source"], a["id"]))
                else:
                    c.execute("UPDATE alerts SET last_value=?, last_source=? WHERE id=?", (value, snap["source"], a["id"]))
            if hit:
                triggered.append({**a, "last_value": value, "last_source": snap["source"],
                                  "message": f"{sym}: {a['kind_label'].lower()} {a['threshold']:g} (valor actual {value:.4g}, {snap['source']})"})
        return {"triggered": triggered, "skipped": skipped, "evaluated": len(active)}

    @staticmethod
    def _snapshot(service, sym: str) -> dict:
        try:
            ps = service.get_series(sym)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"sin datos ({exc})"}
        if ps.is_synthetic:
            return {"error": "solo hay datos sintéticos: la alerta no se evalúa con datos de ejemplo"}
        close = ps.df["close"]
        price, source = float(close.iloc[-1]), f"{ps.prov.provider}, {ps.prov.status_label if hasattr(ps.prov, 'status_label') else ps.prov.status}"
        prev = float(close.iloc[-2]) if len(close) > 1 else None
        change = (price / prev - 1) * 100 if prev else None
        try:
            live = service.get_live(sym)
            price, source = live.price, f"{live.provider}, tiempo real"
            if live.change_pct_today is not None:
                change = live.change_pct_today * 100
        except Exception:  # noqa: BLE001, S110 - sin precio en vivo se usa el cierre diario
            pass
        rsi = ind.rsi(close, 14).iloc[-1]
        return {"price": price, "rsi": None if math.isnan(rsi) else float(rsi), "change_pct": change, "source": source}
