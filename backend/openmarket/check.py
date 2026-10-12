"""Prueba cada proveedor EN VIVO. Úsalo desde la terminal (`python -m openmarket.check`) o desde Configuración.

No usa caché ni datos sintéticos: pide datos reales por proveedor y valida su formato.
"""
from __future__ import annotations

import sys

from .catalog import CATALOG
from .config import Settings, load_settings
from .models import clean_frame
from .service import DataService

DAILY_SAMPLES = {"stooq": ["AAPL", "SPX", "XAUUSD"], "kraken": ["BTC-USD"], "frankfurter": ["EURUSD"]}
LIVE_SAMPLES = {"kraken_live": "BTC-USD", "finnhub": "AAPL"}


def run_checks(service: DataService, settings: Settings) -> list[dict]:
    out: list[dict] = []
    for name, symbols in DAILY_SAMPLES.items():
        for sym in symbols:
            try:
                raw, _ = service.providers[name].fetch_daily(CATALOG[sym], 1)
                df = clean_frame(raw)
                out.append({"provider": name, "kind": "diario", "symbol": sym, "ok": True,
                            "detail": f"{len(df)} barras, último {df.index[-1].date()} cierre {df['close'].iloc[-1]:.4f}"})
            except Exception as exc:  # noqa: BLE001 - se informa de cualquier fallo
                out.append({"provider": name, "kind": "diario", "symbol": sym, "ok": False, "detail": str(exc)})
    for name, sym in LIVE_SAMPLES.items():
        p = service.live_providers[name]
        if not p.available():
            out.append({"provider": name, "kind": "en vivo", "symbol": sym, "ok": False,
                        "detail": "sin clave configurada (OPENMARKET_FINNHUB_KEY): omitido"})
            continue
        try:
            q = p.fetch_quote(CATALOG[sym])
            out.append({"provider": name, "kind": "en vivo", "symbol": sym, "ok": True,
                        "detail": f"{q.price:.4f} {q.currency} a las {q.as_of}"})
        except Exception as exc:  # noqa: BLE001
            out.append({"provider": name, "kind": "en vivo", "symbol": sym, "ok": False, "detail": str(exc)})
    if settings.offline:
        out.insert(0, {"provider": "—", "kind": "aviso", "symbol": "", "ok": False,
                       "detail": "Modo sin conexión activado (OPENMARKET_OFFLINE): desactívalo para probar."})
    return out


def main() -> int:
    from .db import Database
    s = load_settings()
    db = Database(s)
    db.init()
    results = run_checks(DataService(s, db), s)
    failures = 0
    for r in results:
        flag = "OK   " if r["ok"] else "FALLO"
        failures += 0 if r["ok"] else 1
        print(f"{flag} {r['provider']:12} {r['kind']:8} {r['symbol']:8} {r['detail']}")
    print("\nTodo correcto." if not failures else f"\n{failures} comprobación(es) fallida(s). Pega esta salida en un issue para ajustar el proveedor.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
