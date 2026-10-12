"""Catálogo de activos y normalización de símbolos.

Cada activo declara qué proveedores pueden servirlo y con qué código propio.
Los códigos de proveedor NO están verificados contra servicio en vivo desde el entorno de
desarrollo (sin acceso de red a esos proveedores); si un código falla, el proveedor lo
registra como error y el sistema muestra la procedencia real del dato.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES: dict[str, str] = {
    "stock": "Acciones",
    "etf": "ETF y fondos",
    "crypto": "Criptomonedas",
    "forex": "Forex",
    "commodity": "Materias primas",
    "index": "Índices",
}

# Periodos por año para anualizar (cripto negocia 24/7)
PERIODS_PER_YEAR = {"crypto": 365, "forex": 260}
DEFAULT_PERIODS_PER_YEAR = 252


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    category: str
    market: str
    currency: str
    providers: dict[str, str] = field(default_factory=dict)  # proveedor -> código propio
    note: str = ""

    @property
    def periods_per_year(self) -> int:
        return PERIODS_PER_YEAR.get(self.category, DEFAULT_PERIODS_PER_YEAR)

    def public(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "category": self.category,
            "category_label": CATEGORIES[self.category],
            "market": self.market,
            "currency": self.currency,
            "note": self.note,
        }


def _stock(sym, name, market, cur, stooq):
    return Asset(sym, name, "stock", market, cur, {"stooq": stooq})


def _etf(sym, name, market, cur, stooq):
    return Asset(sym, name, "etf", market, cur, {"stooq": stooq})


def _index(sym, name, market, stooq):
    return Asset(
        sym, name, "index", market, "PTS", {"stooq": stooq},
        note="Índice estadístico: no se puede comprar directamente; use un ETF o futuro que lo replique.",
    )


def _crypto(sym, name, kraken):
    return Asset(
        sym, name, "crypto", "Kraken (spot)", "USD", {"kraken": kraken},
        note="Cotización de un único exchange (Kraken); otros exchanges pueden diferir.",
    )


def _fx(sym, base, quote, name):
    return Asset(
        sym, name, "forex", "Tipo de cambio de referencia", quote, {"frankfurter": f"{base}/{quote}"},
        note="Tipo de cambio de referencia diario (BCE). Indicativo: no es un precio ejecutable.",
    )


def _cmdty(sym, name, cur, stooq, note):
    return Asset(sym, name, "commodity", "Spot / futuros", cur, {"stooq": stooq}, note=note)


_ASSETS: list[Asset] = [
    # Acciones
    _stock("AAPL", "Apple", "NASDAQ", "USD", "aapl.us"),
    _stock("MSFT", "Microsoft", "NASDAQ", "USD", "msft.us"),
    _stock("NVDA", "NVIDIA", "NASDAQ", "USD", "nvda.us"),
    _stock("AMZN", "Amazon", "NASDAQ", "USD", "amzn.us"),
    _stock("GOOGL", "Alphabet (A)", "NASDAQ", "USD", "googl.us"),
    _stock("TSLA", "Tesla", "NASDAQ", "USD", "tsla.us"),
    _stock("JPM", "JPMorgan Chase", "NYSE", "USD", "jpm.us"),
    _stock("XOM", "Exxon Mobil", "NYSE", "USD", "xom.us"),
    _stock("SAN", "Banco Santander", "BME", "EUR", "san.es"),
    _stock("ITX", "Inditex", "BME", "EUR", "itx.es"),
    _stock("IBE", "Iberdrola", "BME", "EUR", "ibe.es"),
    _stock("SAP", "SAP", "XETRA", "EUR", "sap.de"),
    # ETF
    _etf("SPY", "SPDR S&P 500 ETF", "NYSE Arca", "USD", "spy.us"),
    _etf("QQQ", "Invesco QQQ (Nasdaq-100)", "NASDAQ", "USD", "qqq.us"),
    _etf("VTI", "Vanguard Total Stock Market", "NYSE Arca", "USD", "vti.us"),
    _etf("EFA", "iShares MSCI EAFE", "NYSE Arca", "USD", "efa.us"),
    _etf("GLD", "SPDR Gold Shares", "NYSE Arca", "USD", "gld.us"),
    _etf("TLT", "iShares 20+ Year Treasury", "NASDAQ", "USD", "tlt.us"),
    # Cripto
    _crypto("BTC-USD", "Bitcoin", "XBTUSD"),
    _crypto("ETH-USD", "Ethereum", "ETHUSD"),
    _crypto("SOL-USD", "Solana", "SOLUSD"),
    _crypto("XRP-USD", "XRP", "XRPUSD"),
    # Forex
    _fx("EURUSD", "EUR", "USD", "Euro / Dólar"),
    _fx("EURGBP", "EUR", "GBP", "Euro / Libra"),
    _fx("EURJPY", "EUR", "JPY", "Euro / Yen"),
    _fx("EURCHF", "EUR", "CHF", "Euro / Franco suizo"),
    _fx("USDJPY", "USD", "JPY", "Dólar / Yen"),
    _fx("GBPUSD", "GBP", "USD", "Libra / Dólar"),
    # Materias primas
    _cmdty("XAUUSD", "Oro (spot)", "USD", "xauusd", "Precio spot; no equivale a un futuro ni al ETF GLD."),
    _cmdty("XAGUSD", "Plata (spot)", "USD", "xagusd", "Precio spot; no equivale a un futuro."),
    _cmdty("WTI", "Petróleo WTI (futuro continuo)", "USD", "cl.f", "Futuro continuo: puede incluir saltos al cambiar de vencimiento."),
    _cmdty("NATGAS", "Gas natural (futuro continuo)", "USD", "ng.f", "Futuro continuo: puede incluir saltos al cambiar de vencimiento."),
    _cmdty("COPPER", "Cobre (futuro continuo)", "USD", "hg.f", "Futuro continuo: puede incluir saltos al cambiar de vencimiento."),
    # Índices
    _index("SPX", "S&P 500", "EE. UU.", "^spx"),
    _index("NDX", "Nasdaq 100", "EE. UU.", "^ndx"),
    _index("DJI", "Dow Jones", "EE. UU.", "^dji"),
    _index("IBEX", "IBEX 35", "España", "^ibex"),
    _index("DAX", "DAX 40", "Alemania", "^dax"),
    _index("FTSE", "FTSE 100", "Reino Unido", "^ukx"),
    _index("N225", "Nikkei 225", "Japón", "^nkx"),
    _index("HSI", "Hang Seng", "Hong Kong", "^hsi"),
]

CATALOG: dict[str, Asset] = {a.symbol: a for a in _ASSETS}

# Alias comunes -> símbolo canónico
_ALIASES = {
    "BTC": "BTC-USD", "BTCUSD": "BTC-USD", "XBT": "BTC-USD", "ETH": "ETH-USD", "ETHUSD": "ETH-USD",
    "SOL": "SOL-USD", "XRP": "XRP-USD", "EUR/USD": "EURUSD", "EUR-USD": "EURUSD", "GOLD": "XAUUSD",
    "ORO": "XAUUSD", "SILVER": "XAGUSD", "PLATA": "XAGUSD", "OIL": "WTI", "PETROLEO": "WTI",
    "^GSPC": "SPX", "S&P500": "SPX", "SP500": "SPX", "^IXIC": "NDX", "^DJI": "DJI", "^IBEX": "IBEX",
    "^GDAXI": "DAX", "^FTSE": "FTSE", "^N225": "N225", "^HSI": "HSI",
}

DEFAULT_DASHBOARD = [
    "SPX", "NDX", "DJI", "IBEX", "DAX", "FTSE", "N225", "HSI",
    "AAPL", "MSFT", "NVDA", "SAN", "BTC-USD", "ETH-USD", "EURUSD", "XAUUSD", "WTI", "SPY",
]


def normalize_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    return _ALIASES.get(s, s)


def get_asset(raw: str) -> Asset | None:
    return CATALOG.get(normalize_symbol(raw))


def search(query: str, limit: int = 15) -> list[Asset]:
    q = (query or "").strip().lower()
    if not q:
        return []
    scored: list[tuple[int, Asset]] = []
    for a in CATALOG.values():
        sym, name = a.symbol.lower(), a.name.lower()
        if sym == q:
            score = 0
        elif sym.startswith(q):
            score = 1
        elif name.startswith(q):
            score = 2
        elif q in sym or q in name:
            score = 3
        else:
            continue
        scored.append((score, a))
    scored.sort(key=lambda t: (t[0], t[1].symbol))
    return [a for _, a in scored[:limit]]
