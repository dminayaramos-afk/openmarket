"""`python -m openmarket.check` — prueba cada proveedor EN VIVO desde tu equipo y explica qué falla.

No usa caché ni datos sintéticos: pide una serie real por proveedor y valida su formato.
"""
from __future__ import annotations

import sys

from .catalog import CATALOG
from .config import load_settings
from .models import clean_frame
from .providers.frankfurter import FrankfurterProvider
from .providers.kraken import KrakenProvider
from .providers.stooq import StooqProvider

SAMPLES = {"stooq": ["AAPL", "SPX", "XAUUSD"], "kraken": ["BTC-USD"], "frankfurter": ["EURUSD"]}


def main() -> int:
    s = load_settings()
    providers = {"stooq": StooqProvider(s), "kraken": KrakenProvider(s), "frankfurter": FrankfurterProvider(s)}
    failures = 0
    for name, symbols in SAMPLES.items():
        for sym in symbols:
            asset = CATALOG[sym]
            try:
                raw, _note = providers[name].fetch_daily(asset, 1)
                df = clean_frame(raw)
                last = df.iloc[-1]
                print(f"OK    {name:12} {sym:8} {len(df):4} barras, último {df.index[-1].date()} cierre {last['close']:.4f}")
            except Exception as exc:  # noqa: BLE001 - se informa de cualquier fallo
                failures += 1
                print(f"FALLO {name:12} {sym:8} {exc}")
    print("\nTodo correcto." if not failures else f"\n{failures} comprobación(es) fallida(s). Pega esta salida en un issue para ajustar el proveedor.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
