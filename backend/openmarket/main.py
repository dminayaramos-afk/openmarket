"""API de OpenMarket (FastAPI). Sirve también el frontend compilado si existe (frontend/dist)."""
from __future__ import annotations

import contextlib
import csv
import hmac
import io
import math
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .analysis import backtest as bt
from .analysis import indicators as ind
from .analysis import signals as sig
from .analysis.risk import correlation_matrix, risk_metrics
from .catalog import CATALOG, CATEGORIES, DEFAULT_DASHBOARD, get_asset, search
from .config import Settings, load_settings
from .db import Database
from .models import DataUnavailable, PriceSeries
from .portfolio import PortfolioError, PortfolioStore, paper_fill_price
from .service import DataService

# Estado real de cada sección de la navegación (la interfaz lo refleja tal cual)
MODULES = [
    {"id": "dashboard", "label": "Dashboard", "status": "available", "route": "/"},
    {"id": "markets", "label": "Mercados globales", "status": "available", "route": "/mercados"},
    {"id": "stock", "label": "Acciones", "status": "available", "route": "/mercado/stock"},
    {"id": "etf", "label": "ETF y fondos", "status": "partial", "route": "/mercado/etf",
     "note": "ETF sí; fondos de inversión, comisiones y composición aún no."},
    {"id": "crypto", "label": "Criptomonedas", "status": "partial", "route": "/mercado/crypto",
     "note": "Solo Kraken spot; sin comparación entre exchanges ni métricas on-chain."},
    {"id": "forex", "label": "Forex", "status": "partial", "route": "/mercado/forex",
     "note": "Referencia diaria del BCE (indicativa); sin OHLC ni comparación entre fuentes."},
    {"id": "commodity", "label": "Materias primas", "status": "partial", "route": "/mercado/commodity",
     "note": "Sin análisis de curva de futuros (contango/backwardation)."},
    {"id": "index", "label": "Índices", "status": "available", "route": "/mercado/index"},
    {"id": "bonds", "label": "Bonos", "status": "planned", "route": None},
    {"id": "derivatives", "label": "Derivados", "status": "planned", "route": None},
    {"id": "screener", "label": "Buscador de oportunidades", "status": "planned", "route": None},
    {"id": "quant", "label": "Análisis cuantitativo", "status": "available", "route": "/mercados",
     "note": "Señales, probabilidades empíricas y validación walk-forward en cada ficha."},
    {"id": "ai", "label": "IA financiera", "status": "planned", "route": None},
    {"id": "portfolios", "label": "Carteras", "status": "available", "route": "/carteras"},
    {"id": "risk", "label": "Gestión del riesgo", "status": "partial", "route": "/carteras",
     "note": "Volatilidad, drawdown, VaR histórico y concentración; sin escenarios adversos ni tamaño de posición."},
    {"id": "simulator", "label": "Simulador", "status": "available", "route": "/carteras",
     "note": "Paper trading con carteras simuladas."},
    {"id": "backtest", "label": "Backtesting", "status": "available", "route": "/backtesting"},
    {"id": "alerts", "label": "Alertas", "status": "planned", "route": None},
    {"id": "news", "label": "Noticias y calendario", "status": "planned", "route": None},
    {"id": "settings", "label": "Configuración", "status": "available", "route": "/configuracion"},
]


NO_FRONTEND_HTML = """<!doctype html><html lang="es"><meta charset="utf-8"><title>OpenMarket</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:10vh auto;padding:0 16px;line-height:1.5;background:#060b1d;color:#e8ecfa">
<h1>OpenMarket: la API funciona, pero falta la interfaz</h1>
<p>No se encontró el frontend compilado (<code>frontend/dist</code>). La API está activa: puedes ver su
documentación en <a style="color:#5b8cff" href="/api/docs">/api/docs</a>.</p>
<p>Para tener la interfaz, usa el repositorio completo (incluye <code>frontend/dist</code>) o compílala con
Node.js 20+: <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code> y reinicia.</p></body></html>"""


def sanitize(obj):
    """NaN/inf → None, tipos NumPy → nativos (JSON estricto)."""
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        with contextlib.suppress(AttributeError, ValueError, TypeError):
            obj = obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def respond(data, status: int = 200) -> JSONResponse:
    return JSONResponse(sanitize(data), status_code=status)


# --- modelos de entrada -------------------------------------------------------------------------
class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_currency: str = Field(default="USD", pattern=r"^[A-Za-z]{3}$")
    paper: bool = False


class TxIn(BaseModel):
    type: Literal["buy", "sell", "deposit", "withdraw"]
    symbol: str | None = Field(default=None, max_length=20)
    quantity: float | None = Field(default=None, gt=0, lt=1e12)
    price: float | None = Field(default=None, gt=0, lt=1e12)
    fee: float = Field(default=0.0, ge=0, lt=1e9)
    amount: float | None = Field(default=None, gt=0, lt=1e12)
    ts: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=500)


class PaperOrderIn(BaseModel):
    symbol: str = Field(max_length=20)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, lt=1e12)


class BacktestIn(BaseModel):
    symbol: str = Field(max_length=20)
    strategy: Literal["buy_hold", "sma_cross", "rsi_reversion", "breakout"] = "sma_cross"
    params: dict[str, float] = Field(default_factory=dict)
    initial_capital: float = Field(default=10_000.0, gt=0, le=1e9)
    commission_bps: float | None = Field(default=None, ge=0, le=500)
    slippage_bps: float | None = Field(default=None, ge=0, le=500)
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    oos_fraction: float | None = Field(default=None, ge=0.05, le=0.8)
    years: int = Field(default=5, ge=1, le=20)


def _f(x):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else float(x)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings)
    db.init()
    service = DataService(settings, db)
    store = PortfolioStore(db)

    app = FastAPI(title="OpenMarket", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings, app.state.service, app.state.store = settings, service, store

    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def auth_and_headers(request: Request, call_next):
        path = request.url.path
        if settings.api_token and path.startswith("/api") and path != "/api/health" and request.method != "OPTIONS":
            supplied = request.headers.get("authorization", "")
            expected = f"Bearer {settings.api_token}"
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                return JSONResponse({"detail": "No autorizado: falta o es incorrecto el token (Authorization: Bearer …)."},
                                    status_code=401)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    # --- helpers -------------------------------------------------------------------------------
    def series_or_error(symbol: str, years: int = 5, refresh: bool = False) -> PriceSeries:
        if get_asset(symbol) is None:
            raise HTTPException(404, f"Símbolo desconocido: {symbol}")
        try:
            return service.get_series(symbol, years, refresh)
        except DataUnavailable as exc:
            raise HTTPException(503, f"Sin datos disponibles para {symbol}: {exc}") from exc

    def quote_of(sym: str, ps: PriceSeries) -> dict:
        a = CATALOG[sym]
        close = ps.df["close"]
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else None
        return {
            **a.public(), "price": last, "prev_close": prev,
            "change": (last - prev) if prev else None,
            "change_pct": (last / prev - 1) if prev else None,
            "as_of": ps.prov.as_of, "provenance": ps.prov.public(),
            "spark": [round(float(x), 6) for x in close.iloc[-40:]],
        }

    # --- generales -------------------------------------------------------------------------------
    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "offline": settings.offline,
                "demo_fallback": settings.demo_fallback, "auth_required": bool(settings.api_token)}

    @app.get("/api/modules")
    def modules():
        return respond({"modules": MODULES, "categories": CATEGORIES})

    @app.get("/api/search")
    def search_assets(q: str = Query(min_length=1, max_length=40)):
        return respond({"results": [a.public() for a in search(q)]})

    @app.get("/api/assets")
    def list_assets(category: str | None = Query(default=None, max_length=20)):
        items = [a.public() for a in CATALOG.values() if category in (None, a.category)]
        return respond({"assets": items})

    @app.get("/api/sources")
    def sources():
        return respond({"sources": service.sources_status(), "offline": settings.offline,
                        "demo_fallback": settings.demo_fallback})

    @app.get("/api/quotes")
    def quotes(symbols: str | None = Query(default=None, max_length=600), category: str | None = None):
        if symbols:
            syms = [get_asset(s).symbol for s in symbols.split(",") if s.strip() and get_asset(s)]
        elif category:
            syms = [a.symbol for a in CATALOG.values() if a.category == category]
        else:
            syms = list(DEFAULT_DASHBOARD)
        syms = list(dict.fromkeys(syms))[:60]
        results = service.get_many(syms, years=5)
        out, errors = [], {}
        for s, r in results.items():
            if isinstance(r, Exception):
                errors[s] = str(r)
            else:
                out.append(quote_of(s, r))
        stamps = [q["provenance"]["fetched_at"] for q in out if q["provenance"]["fetched_at"]]
        return respond({"quotes": out, "errors": errors, "last_update": max(stamps) if stamps else None,
                        "any_synthetic": any(q["provenance"]["status"] == "synthetic" for q in out)})

    @app.get("/api/correlations")
    def correlations(symbols: str = Query(max_length=300)):
        syms = list(dict.fromkeys(get_asset(s).symbol for s in symbols.split(",") if get_asset(s)))[:12]
        if len(syms) < 2:
            raise HTTPException(422, "Indique al menos dos símbolos válidos")
        got = service.get_many(syms)
        closes = {s: r.df["close"] for s, r in got.items() if not isinstance(r, Exception)}
        res = correlation_matrix(closes)
        res["any_synthetic"] = any(r.is_synthetic for r in got.values() if not isinstance(r, Exception))
        return respond(res)

    # --- ficha de activo --------------------------------------------------------------------------
    @app.get("/api/assets/{symbol}")
    def asset_detail(symbol: str, refresh: bool = False, validate: bool = True):
        ps = series_or_error(symbol, 5, refresh)
        asset = CATALOG[get_asset(symbol).symbol]
        df, close = ps.df, ps.df["close"]
        macd = ind.macd(close)
        bb = ind.bollinger(close)
        adx = ind.adx(df)
        vw = ind.vwap_rolling(df)
        last = lambda s: _f(s.iloc[-1]) if s is not None and len(s) else None
        indicators = {
            "sma20": last(ind.sma(close, 20)), "sma50": last(ind.sma(close, 50)), "sma200": last(ind.sma(close, 200)),
            "ema12": last(ind.ema(close, 12)), "ema26": last(ind.ema(close, 26)),
            "rsi14": last(ind.rsi(close)), "macd": last(macd["macd"]), "macd_signal": last(macd["signal"]),
            "macd_hist": last(macd["hist"]), "bb_upper": last(bb["upper"]), "bb_lower": last(bb["lower"]),
            "bb_pct_b": last(bb["pct_b"]), "atr14": last(ind.atr(df)), "adx14": last(adx["adx"]),
            "momentum20": last(ind.momentum(close, 20)),
            "vol20_annualized": last(ind.realized_vol(close, 20, asset.periods_per_year)),
            "vwap20": last(vw) if vw is not None else None,
        }
        notes = []
        if vw is None:
            notes.append("VWAP y volumen no disponibles para este tipo de dato (sin volumen real).")
        if df["volume"].sum() <= 0:
            notes.append("Este activo no tiene volumen en la fuente utilizada.")
        return respond({
            "asset": asset.public(), "provenance": ps.prov.public(), "quote": quote_of(asset.symbol, ps),
            "bars": len(df), "first_date": df.index[0].date().isoformat(), "last_date": df.index[-1].date().isoformat(),
            "indicators": indicators, "returns": ind.period_returns(close, asset.periods_per_year),
            "levels": ind.support_resistance(df), "risk": risk_metrics(close, asset.periods_per_year),
            "signal": sig.build_signal(df, with_validation=validate), "notes": notes,
        })

    @app.get("/api/assets/{symbol}/chart")
    def asset_chart(symbol: str, bars: int = Query(default=520, ge=30, le=3000)):
        ps = series_or_error(symbol)
        df, c = ps.df, ps.df["close"]
        bb, macd, rsi = ind.bollinger(c), ind.macd(c), ind.rsi(c)
        sl = df.index[-bars:]

        def line(s: pd.Series):
            s = s.reindex(sl).dropna()
            return [{"time": d.date().isoformat(), "value": round(float(v), 6)} for d, v in s.items()]

        candles = [
            {"time": d.date().isoformat(), "open": float(r.open), "high": float(r.high), "low": float(r.low),
             "close": float(r.close)} for d, r in df.loc[sl].iterrows()
        ]
        volume = [{"time": d.date().isoformat(), "value": float(v), "up": bool(c.loc[d] >= df.loc[d, "open"])}
                  for d, v in df.loc[sl, "volume"].items()] if df["volume"].sum() > 0 else []
        macd_hist = macd["hist"].reindex(sl).dropna()
        return respond({
            "symbol": CATALOG[get_asset(symbol).symbol].symbol, "provenance": ps.prov.public(),
            "candles": candles, "volume": volume,
            "overlays": {"sma20": line(ind.sma(c, 20)), "sma50": line(ind.sma(c, 50)), "sma200": line(ind.sma(c, 200)),
                         "bb_upper": line(bb["upper"]), "bb_lower": line(bb["lower"])},
            "rsi": line(rsi), "macd": line(macd["macd"]), "macd_signal": line(macd["signal"]),
            "macd_hist": [{"time": d.date().isoformat(), "value": round(float(v), 6)} for d, v in macd_hist.items()],
        })

    # --- listas de seguimiento ---------------------------------------------------------------------
    @app.get("/api/watchlist")
    def watchlist_get():
        with db.connect() as c:
            rows = c.execute("SELECT symbol FROM watchlist ORDER BY added_at, symbol").fetchall()
        return respond({"symbols": [r["symbol"] for r in rows]})

    @app.post("/api/watchlist/{symbol}")
    def watchlist_add(symbol: str):
        a = get_asset(symbol)
        if a is None:
            raise HTTPException(404, "Símbolo desconocido")
        with db.connect() as c:
            c.execute("INSERT OR IGNORE INTO watchlist(symbol, added_at) VALUES (?, datetime('now'))", (a.symbol,))
        return watchlist_get()

    @app.delete("/api/watchlist/{symbol}")
    def watchlist_remove(symbol: str):
        a = get_asset(symbol)
        with db.connect() as c:
            c.execute("DELETE FROM watchlist WHERE symbol=?", (a.symbol if a else symbol,))
        return watchlist_get()

    # --- backtesting ---------------------------------------------------------------------------------
    @app.get("/api/strategies")
    def strategies():
        return respond({"strategies": [{"id": k, **v} for k, v in bt.STRATEGIES.items()]})

    @app.post("/api/backtest")
    def backtest(body: BacktestIn):
        ps = series_or_error(body.symbol, body.years)
        asset = CATALOG[get_asset(body.symbol).symbol]
        cfg = bt.Config(
            strategy=body.strategy, params=body.params, initial_capital=body.initial_capital,
            commission_bps=settings.commission_bps if body.commission_bps is None else body.commission_bps,
            slippage_bps=settings.slippage_bps if body.slippage_bps is None else body.slippage_bps,
            start=body.start, end=body.end, oos_fraction=body.oos_fraction,
        )
        try:
            result = bt.run(ps.df, cfg, asset.periods_per_year)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        result["symbol"], result["provenance"] = asset.symbol, ps.prov.public()
        if ps.is_synthetic:
            result["warnings"].insert(0, "ATENCIÓN: este backtest usa datos SINTÉTICOS; los resultados no representan el mercado real.")
        return respond(result)

    # --- carteras y paper trading --------------------------------------------------------------------
    def pf_or_404(pid: int) -> dict:
        try:
            return store.get(pid)
        except KeyError as exc:
            raise HTTPException(404, "Cartera no encontrada") from exc

    @app.get("/api/portfolios")
    def portfolios_list():
        return respond({"portfolios": store.list()})

    @app.post("/api/portfolios", status_code=201)
    def portfolios_create(body: PortfolioIn):
        return respond(store.create(body.name, body.base_currency, body.paper), 201)

    @app.delete("/api/portfolios/{pid}")
    def portfolios_delete(pid: int):
        pf_or_404(pid)
        store.delete(pid)
        return respond({"deleted": pid})

    @app.get("/api/portfolios/{pid}")
    def portfolio_summary(pid: int):
        pf_or_404(pid)
        state = store.positions_state(pid)
        got = service.get_many(list(state["positions"].keys()))
        series = {s: r for s, r in got.items() if not isinstance(r, Exception)}
        res = store.summary(pid, series)
        res["transactions"] = store.transactions(pid)
        for s, r in got.items():
            if isinstance(r, Exception):
                res["warnings"].append(f"{s}: sin datos de precio ({r}).")
        return respond(res)

    @app.post("/api/portfolios/{pid}/transactions", status_code=201)
    def portfolio_tx(pid: int, body: TxIn):
        pf_or_404(pid)
        try:
            tx = store.add_transaction(pid, body.model_dump())
        except PortfolioError as exc:
            raise HTTPException(422, str(exc)) from exc
        return respond(tx, 201)

    @app.post("/api/portfolios/{pid}/paper-order", status_code=201)
    def paper_order(pid: int, body: PaperOrderIn):
        pf = pf_or_404(pid)
        if not pf["paper"]:
            raise HTTPException(422, "Solo las carteras de paper trading aceptan órdenes simuladas")
        ps = series_or_error(body.symbol)
        asset = CATALOG[get_asset(body.symbol).symbol]
        if asset.currency != pf["base_currency"]:
            raise HTTPException(422, f"{asset.symbol} cotiza en {asset.currency}; esta cartera usa {pf['base_currency']} "
                                     "(no hay conversión de divisas).")
        px = paper_fill_price(float(ps.df["close"].iloc[-1]), body.side, settings.slippage_bps)
        fee = body.quantity * px * settings.commission_bps / 10_000
        note = (f"Orden simulada al último cierre {ps.prov.as_of} ({ps.prov.provider}, {ps.prov.status}) "
                f"con slippage {settings.slippage_bps} pb y comisión {settings.commission_bps} pb")
        if ps.is_synthetic:
            note = "[DATO SINTÉTICO] " + note
        try:
            tx = store.add_transaction(pid, {"type": body.side, "symbol": asset.symbol, "quantity": body.quantity,
                                             "price": px, "fee": fee, "note": note}, enforce_cash=True)
        except PortfolioError as exc:
            raise HTTPException(422, str(exc)) from exc
        return respond(tx, 201)

    @app.get("/api/portfolios/{pid}/export.csv")
    def portfolio_export(pid: int):
        pf_or_404(pid)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ts", "type", "symbol", "quantity", "price", "fee", "amount", "note"])
        for t in store.transactions(pid):
            w.writerow([t["ts"], t["type"], t["symbol"] or "", t["quantity"] or "", t["price"] or "", t["fee"],
                        t["amount"] or "", t["note"]])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="cartera-{pid}.csv"'})

    @app.post("/api/portfolios/{pid}/import")
    def portfolio_import(pid: int, csv_text: str = Body(media_type="text/csv", max_length=2_000_000)):
        pf_or_404(pid)
        reader = csv.DictReader(io.StringIO(csv_text))
        n, errors = 0, []
        for i, row in enumerate(reader, start=2):
            if i > 5002:
                errors.append("Máximo 5000 filas por importación")
                break
            try:
                tx = TxIn(
                    type=row["type"].strip().lower(), symbol=(row.get("symbol") or None),
                    quantity=float(row["quantity"]) if row.get("quantity") else None,
                    price=float(row["price"]) if row.get("price") else None,
                    fee=float(row["fee"]) if row.get("fee") else 0.0,
                    amount=float(row["amount"]) if row.get("amount") else None,
                    ts=row.get("ts") or None, note=row.get("note") or None,
                )
                store.add_transaction(pid, tx.model_dump())
                n += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Fila {i}: {exc}")
        return respond({"imported": n, "errors": errors[:50]})

    # --- frontend compilado --------------------------------------------------------------------------
    dist = Path(settings.frontend_dist)
    if (dist / "index.html").is_file():
        dist_root = dist.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404, "No encontrado")
            candidate = (dist_root / full_path).resolve()
            if full_path and dist_root in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist_root / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def no_frontend():
            return HTMLResponse(NO_FRONTEND_HTML, status_code=200)

    return app


def app_factory() -> FastAPI:  # para `uvicorn openmarket.main:app_factory --factory`
    return create_app()


app = create_app()  # `uvicorn openmarket.main:app`
