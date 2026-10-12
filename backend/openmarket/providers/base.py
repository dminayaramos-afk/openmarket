"""Capa común para proveedores: cliente HTTP con reintentos, límite de frecuencia y registro de salud."""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
import pandas as pd

from ..catalog import Asset
from ..models import ProviderError, utcnow_iso

# Inyectable en pruebas (httpx.MockTransport). En producción es None -> red real.
_TRANSPORT: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _TRANSPORT
    _TRANSPORT = transport


@dataclass
class Health:
    ok_count: int = 0
    error_count: int = 0
    last_ok: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None


class _ClientError(Exception):
    """Error 4xx: no es un fallo del servicio."""


class Provider(ABC):
    name: str = ""
    label: str = ""
    description: str = ""
    license_note: str = ""
    covers: tuple[str, ...] = ()
    min_interval: float = 0.5  # segundos entre solicitudes
    retries: int = 2
    timeout: float = 10.0
    max_history_note: str = ""
    breaker_threshold: int = 3      # fallos de red/5xx consecutivos que abren el cortacircuitos
    breaker_cooldown: float = 120.0  # segundos sin llamar al proveedor tras abrirse

    def __init__(self) -> None:
        self.health = Health()
        self._lock = threading.Lock()
        self._last_call = 0.0
        self._consecutive_failures = 0
        self._paused_until = 0.0

    def _breaker_open(self) -> bool:
        return time.monotonic() < self._paused_until

    def _note_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.breaker_threshold:
            self._paused_until = time.monotonic() + self.breaker_cooldown
            self._consecutive_failures = 0

    def _note_success(self) -> None:
        self._consecutive_failures = 0

    # --- a implementar -------------------------------------------------------------------
    @abstractmethod
    def fetch_daily(self, asset: Asset, years: int) -> tuple[pd.DataFrame, str]:
        """Devuelve (DataFrame OHLCV con índice de fechas, nota de procedencia)."""

    def supports(self, asset: Asset) -> bool:
        return self.name in asset.providers

    # --- utilidades ----------------------------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def http_get(self, url: str, params: dict | None = None) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            if self._breaker_open():
                raise ProviderError(
                    f"{self.name}: en pausa tras fallos consecutivos (se reintentará en unos minutos)"
                )
            self._throttle()
            try:
                with httpx.Client(timeout=self.timeout, transport=_TRANSPORT, follow_redirects=True,
                                  headers={"User-Agent": "OpenMarket/0.1 (self-hosted)"}) as client:
                    resp = client.get(url, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    self._note_failure()
                    raise ProviderError(f"{self.name}: HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    # Errores 4xx (salvo 429) son del símbolo/petición: no se reintentan ni abren el cortacircuitos
                    raise _ClientError(f"{self.name}: HTTP {resp.status_code}")
                self._note_success()
                return resp
            except _ClientError as exc:
                last_exc = ProviderError(str(exc))
                break
            except ProviderError as exc:
                last_exc = exc
                if self._breaker_open():
                    break
            except httpx.HTTPError as exc:
                self._note_failure()
                last_exc = ProviderError(f"{self.name}: error de red ({type(exc).__name__})")
            if attempt < self.retries:
                time.sleep(0.4 * (2 ** attempt))
        assert last_exc is not None
        raise last_exc

    def record_ok(self) -> None:
        self.health.ok_count += 1
        self.health.last_ok = utcnow_iso()

    def record_error(self, message: str) -> None:
        self.health.error_count += 1
        self.health.last_error = message
        self.health.last_error_at = utcnow_iso()

    def info(self, enabled: bool) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "license_note": self.license_note,
            "covers": list(self.covers),
            "enabled": enabled,
            "history_note": self.max_history_note,
            "ok_count": self.health.ok_count,
            "error_count": self.health.error_count,
            "last_ok": self.health.last_ok,
            "last_error": self.health.last_error,
            "last_error_at": self.health.last_error_at,
        }
