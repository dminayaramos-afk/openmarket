"""Tipos de cambio de referencia (BCE vía Frankfurter) para convertir carteras. Nunca se inventan."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .models import ProviderError
from .providers.frankfurter import FrankfurterProvider

FX_TTL = 3600.0


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    rate: float
    date: str
    source: str = "BCE vía Frankfurter (referencia, no ejecutable)"


class FxService:
    def __init__(self, provider: FrankfurterProvider, offline: bool = False):
        self.provider = provider
        self.offline = offline
        self._cache: dict[tuple[str, str], tuple[float, FxRate]] = {}
        self._lock = threading.Lock()

    def rate(self, base: str, quote: str) -> FxRate | None:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return FxRate(base, quote, 1.0, "", "misma moneda")
        key = (base, quote)
        with self._lock:
            hit = self._cache.get(key)
        if hit and time.time() - hit[0] < FX_TTL:
            return hit[1]
        if not self.offline:
            try:
                resp = self.provider.http_get(f"{self.provider.settings.frankfurter_url}/latest",
                                              {"base": base, "symbols": quote})
                data = resp.json()
                r = float((data.get("rates") or {})[quote])
                if r <= 0:
                    raise ProviderError("tipo de cambio no válido")
                fx = FxRate(base, quote, r, str(data.get("date", "")))
                self.provider.record_ok()
                with self._lock:
                    self._cache[key] = (time.time(), fx)
                return fx
            except Exception as exc:  # noqa: BLE001 - sin tipo de cambio no se convierte
                if "en pausa" not in str(exc):
                    self.provider.record_error(f"fx {base}/{quote}: {exc}")
        return hit[1] if hit else None  # un tipo caducado es mejor que ninguno, y se informa de su fecha
