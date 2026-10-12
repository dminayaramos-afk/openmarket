import httpx
import pytest

from openmarket.catalog import get_asset
from openmarket.models import ProviderError
from openmarket.providers import base as provider_base
from openmarket.providers.live import parse_finnhub_quote, parse_kraken_ticker

KRAKEN_OK = {"error": [], "result": {"XXBTZUSD": {
    "a": ["65010.0", "1", "1.0"], "b": ["65000.0", "1", "1.0"], "c": ["65005.5", "0.1"],
    "v": ["100", "1234.5"], "h": ["66000", "66500"], "l": ["64000", "63500"], "o": "64000.0"}}}


def kraken_transport(payload=KRAKEN_OK):
    def handler(request):
        assert "Ticker" in request.url.path
        return httpx.Response(200, json=payload)
    provider_base.set_transport(httpx.MockTransport(handler))


def test_parse_kraken():
    q = parse_kraken_ticker(KRAKEN_OK, get_asset("BTC-USD"))
    assert q.price == 65005.5 and q.status == "realtime"
    assert q.bid == 65000.0 and q.ask == 65010.0 and q.volume_24h == 1234.5
    assert q.change_pct_today == pytest.approx(65005.5 / 64000 - 1)


def test_parse_kraken_errors():
    a = get_asset("BTC-USD")
    with pytest.raises(ProviderError):
        parse_kraken_ticker({"error": ["EQuery:Unknown asset pair"], "result": {}}, a)
    with pytest.raises(ProviderError):
        parse_kraken_ticker({"error": [], "result": {}}, a)
    with pytest.raises(ProviderError):
        parse_kraken_ticker({"error": [], "result": {"X": {"c": ["0", "1"]}}}, a)


def test_parse_finnhub():
    a = get_asset("AAPL")
    q = parse_finnhub_quote({"c": 190.5, "dp": 1.5, "h": 191, "l": 188, "o": 189, "pc": 187.7, "t": 1700000000}, a)
    assert q.price == 190.5 and q.change_pct_today == pytest.approx(0.015)
    with pytest.raises(ProviderError):
        parse_finnhub_quote({"c": 0, "t": 0}, a)  # símbolo desconocido / clave inválida


def test_live_endpoint_crypto(client):
    kraken_transport()
    r = client.get("/api/live", params={"symbols": "BTC-USD"})
    assert r.status_code == 200
    q = r.json()["quotes"]["BTC-USD"]
    assert q["price"] == 65005.5 and q["status"] == "realtime"


def test_live_endpoint_no_provider_never_invents(client):
    # acciones sin clave de Finnhub: error explícito, jamás un precio inventado
    r = client.get("/api/live", params={"symbols": "AAPL"})
    body = r.json()
    assert "AAPL" not in body["quotes"]
    assert "OPENMARKET_FINNHUB_KEY" in body["errors"]["AAPL"]


def test_live_failure_reported(client):
    r = client.get("/api/live", params={"symbols": "BTC-USD"})  # el transporte rechaza la red
    assert "BTC-USD" in r.json()["errors"] and not r.json()["quotes"]


def test_live_cache(client):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=KRAKEN_OK)
    provider_base.set_transport(httpx.MockTransport(handler))
    client.get("/api/live", params={"symbols": "BTC-USD"})
    client.get("/api/live", params={"symbols": "BTC-USD"})
    assert len(calls) == 1


def _csv_history(settings, sym="BTC-USD", n=300):
    import os
    os.makedirs(settings.csv_dir, exist_ok=True)
    from tests.conftest import make_ohlc
    make_ohlc(n).rename_axis("Date").to_csv(os.path.join(settings.csv_dir, f"{sym}.csv"))


def test_alert_lifecycle(client, settings):
    _csv_history(settings)
    kraken_transport()
    r = client.post("/api/alerts", json={"symbol": "BTC-USD", "kind": "price_above", "threshold": 60000})
    assert r.status_code == 201
    aid = r.json()["id"]
    res = client.post("/api/alerts/check").json()
    assert any(t["id"] == aid for t in res["triggered"])
    lst = client.get("/api/alerts").json()["alerts"]
    assert lst[0]["triggered_at"] and lst[0]["active"] is False
    assert client.post(f"/api/alerts/{aid}/rearm").status_code == 200
    assert client.delete(f"/api/alerts/{aid}").status_code == 200
    assert client.delete(f"/api/alerts/{aid}").status_code == 404


def test_alert_skips_synthetic(client):
    # sin red la serie es sintética: no se dispara con datos inventados
    client.post("/api/alerts", json={"symbol": "SPY", "kind": "price_above", "threshold": 1})
    res = client.post("/api/alerts/check").json()
    assert res["triggered"] == []


def test_alert_validation(client):
    assert client.post("/api/alerts", json={"symbol": "NOPE", "kind": "price_above", "threshold": 1}).status_code == 422
    assert client.post("/api/alerts", json={"symbol": "SPY", "kind": "raro", "threshold": 1}).status_code == 422


def test_screener(client):
    r = client.get("/api/screener", params={"category": "etf"})
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] and body["any_synthetic"] is True
    scores = [x["score"] for x in body["rows"]]
    assert scores == sorted(scores, reverse=True)
    assert all(x["data_status"] == "synthetic" for x in body["rows"])


def test_option_tool(client):
    base = {"kind": "call", "spot": 100, "strike": 100, "days": 365, "rate": 0.05}
    r = client.post("/api/tools/option", json={**base, "volatility": 0.2})
    assert r.status_code == 200
    assert r.json()["theoretical_price"] == pytest.approx(10.4506, abs=1e-3)  # valor de referencia clásico
    iv = client.post("/api/tools/option", json={**base, "market_price": 10.4506}).json()
    assert iv["volatility_used"] == pytest.approx(0.2, abs=1e-3) and iv["volatility_is_implied"]
    assert client.post("/api/tools/option", json={"spot": 100, "strike": 100, "days": 30}).status_code == 422


def test_bond_tool(client):
    r = client.post("/api/tools/bond", json={"coupon": 0.05, "years": 10, "ytm": 0.05}).json()
    assert r["price"] == pytest.approx(100.0, abs=1e-6)
    back = client.post("/api/tools/bond", json={"coupon": 0.05, "years": 10, "price": 92.5}).json()
    assert back["ytm_is_computed"] and back["ytm"] > 0.05
    assert client.post("/api/tools/bond", json={"coupon": 0.05, "years": 10}).status_code == 422


def test_diagnostics(client):
    r = client.post("/api/diagnostics")
    assert r.status_code == 200 and r.json()["results"]
    assert client.post("/api/diagnostics").status_code == 429
