"""Precios en vivo (no son datos diarios): Kraken (cripto, sin clave) y Finnhub (EE. UU., con clave opcional).

Nunca se devuelve un valor inventado: si el proveedor falla se lanza ProviderError y el servicio decide.
Formatos según la documentación de Kraken (Ticker). El de Finnhub (/quote: c, d, dp, h, l, o, pc, t;
parámetro `token`) NO se ha podido verificar contra la documentación oficial ni contra el servicio real.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from ..catalog import Asset
from ..config import Settings
from ..models import STATUS_REALTIME, LiveQuote, ProviderError
from .base import Provider


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


class QuoteProvider(Provider):
    """Proveedor de precio actual (sin histórico)."""

    def fetch_daily(self, asset: Asset, years: int):
        raise ProviderError(f"{self.name}: solo ofrece precio actual, no histórico")

    def fetch_quote(self, asset: Asset) -> LiveQuote:  # pragma: no cover - interfaz
        raise NotImplementedError

    def available(self) -> bool:
        return True


class KrakenTickerProvider(QuoteProvider):
    name = "kraken_live"
    label = "Kraken (precio en vivo)"
    description = "Precio actual, oferta/demanda y máximos/mínimos del día de pares spot de Kraken (API pública)."
    license_note = "API pública sin clave. Refleja solo el libro de Kraken; otros exchanges pueden cotizar distinto."
    covers = ("crypto",)
    max_history_note = "Solo precio actual."
    min_interval = 0.3

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def supports(self, asset: Asset) -> bool:
        return asset.category == "crypto" and "kraken" in asset.providers

    def fetch_quote(self, asset: Asset) -> LiveQuote:
        pair = asset.providers["kraken"]
        resp = self.http_get(f"{self.settings.kraken_url}/0/public/Ticker", {"pair": pair})
        return parse_kraken_ticker(resp.json(), asset)


def parse_kraken_ticker(payload: dict, asset: Asset) -> LiveQuote:
    if not isinstance(payload, dict):
        raise ProviderError("kraken_live: respuesta inválida")
    if payload.get("error"):
        raise ProviderError(f"kraken_live: {payload['error'][0]}")
    result = payload.get("result") or {}
    if not result:
        raise ProviderError("kraken_live: sin datos")
    t = next(iter(result.values()))
    last = _num((t.get("c") or [None])[0])
    if last is None or last <= 0:
        raise ProviderError("kraken_live: precio no válido")
    open_today = _num(t.get("o"))
    return LiveQuote(
        symbol=asset.symbol, price=last, as_of=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        provider="Kraken (precio en vivo)", status=STATUS_REALTIME, currency=asset.currency,
        open_today=open_today, high_today=_num((t.get("h") or [None])[0]), low_today=_num((t.get("l") or [None])[0]),
        bid=_num((t.get("b") or [None])[0]), ask=_num((t.get("a") or [None])[0]),
        volume_24h=_num((t.get("v") or [None, None])[1]),
        change_pct_today=(last / open_today - 1) if open_today else None,
        note="Último precio negociado en Kraken; el día empieza a las 00:00 UTC.",
    )


class FinnhubProvider(QuoteProvider):
    name = "finnhub"
    label = "Finnhub (precio en vivo)"
    description = "Precio actual de acciones y ETF de EE. UU. (requiere clave gratuita en OPENMARKET_FINNHUB_KEY)."
    license_note = ("Servicio de terceros con clave propia: https://finnhub.io. El plan gratuito permite unas 60 consultas "
                    "por minuto según fuentes secundarias; revisa sus condiciones y si el dato es en tiempo real o retrasado.")
    covers = ("stock", "etf")
    max_history_note = "Solo precio actual. Formato de respuesta sin verificar contra el servicio real."
    min_interval = 0.25

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def available(self) -> bool:
        return bool(self.settings.finnhub_key)

    def supports(self, asset: Asset) -> bool:
        return "finnhub" in asset.providers

    def fetch_quote(self, asset: Asset) -> LiveQuote:
        if not self.settings.finnhub_key:
            raise ProviderError("finnhub: falta la clave gratuita (OPENMARKET_FINNHUB_KEY)")
        resp = self.http_get(f"{self.settings.finnhub_url}/quote",
                             {"symbol": asset.providers["finnhub"], "token": self.settings.finnhub_key})
        return parse_finnhub_quote(resp.json(), asset)


def parse_finnhub_quote(payload: dict, asset: Asset) -> LiveQuote:
    if not isinstance(payload, dict):
        raise ProviderError("finnhub: respuesta inválida")
    price = _num(payload.get("c"))
    if price is None or price <= 0:  # Finnhub devuelve c=0 para símbolos desconocidos
        raise ProviderError("finnhub: sin precio para este símbolo (¿clave inválida o símbolo no cubierto?)")
    ts = _num(payload.get("t"))
    as_of = (datetime.fromtimestamp(ts, tz=timezone.utc) if ts and ts > 0 else datetime.now(timezone.utc))
    pc = _num(payload.get("pc"))
    dp = _num(payload.get("dp"))
    return LiveQuote(
        symbol=asset.symbol, price=price, as_of=as_of.replace(microsecond=0).isoformat(),
        provider="Finnhub (precio en vivo)", status=STATUS_REALTIME, currency=asset.currency,
        open_today=_num(payload.get("o")), high_today=_num(payload.get("h")), low_today=_num(payload.get("l")),
        change_pct_today=(dp / 100.0) if dp is not None else ((price / pc - 1) if pc else None),
        note="Marca temporal del último dato del proveedor; si el mercado está cerrado es el último cierre.",
    )
