from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from openmarket.main import create_app


def test_health_and_modules(client):
    assert client.get("/api/health").json()["status"] == "ok"
    mods = client.get("/api/modules").json()["modules"]
    assert len(mods) == 20 and {m["status"] for m in mods} <= {"available", "partial", "planned"}
    assert [m["label"] for m in mods][:3] == ["Dashboard", "Mercados globales", "Acciones"]


def test_search_and_aliases(client):
    assert client.get("/api/search?q=bitcoin").json()["results"][0]["symbol"] == "BTC-USD"
    assert client.get("/api/search?q=eur").json()["results"]
    assert client.get("/api/assets/BTC").status_code == 200   # alias
    assert client.get("/api/assets/NOPE").status_code == 404
    assert client.get("/api/search?q=").status_code == 422


def test_asset_detail_is_strict_json_and_labeled(client):
    r = client.get("/api/assets/SPX")
    assert r.status_code == 200
    d = r.json()
    assert d["provenance"]["status"] == "synthetic"
    assert d["signal"]["available"] and d["signal"]["direction"] in {"BAJISTA", "NEUTRAL", "ALCISTA"}
    assert "índice estadístico" in d["asset"]["note"].lower()
    assert d["indicators"]["vwap20"] is None and d["notes"]   # índice sin volumen


def test_chart_payload(client):
    d = client.get("/api/assets/ETH-USD/chart?bars=100").json()
    assert len(d["candles"]) == 100 and d["overlays"]["sma20"] and d["rsi"] and d["macd_hist"]
    assert d["candles"][0].keys() >= {"time", "open", "high", "low", "close"}


def test_quotes_and_errors(client):
    d = client.get("/api/quotes?symbols=AAPL,BTC,ZZZZ").json()
    assert {q["symbol"] for q in d["quotes"]} == {"AAPL", "BTC-USD"}
    assert d["any_synthetic"] is True and d["last_update"]
    assert len(client.get("/api/quotes").json()["quotes"]) == 18


def test_correlations(client):
    d = client.get("/api/correlations?symbols=SPX,NDX,BTC-USD").json()
    assert d["available"] and np.allclose(np.diag(np.array(d["matrix"])), 1.0)
    assert client.get("/api/correlations?symbols=SPX").status_code == 422


def test_watchlist(client):
    assert client.get("/api/watchlist").json()["symbols"] == []
    assert client.post("/api/watchlist/aapl").json()["symbols"] == ["AAPL"]
    assert client.delete("/api/watchlist/AAPL").json()["symbols"] == []


def test_backtest_endpoint(client):
    r = client.post("/api/backtest", json={"symbol": "SPY", "strategy": "sma_cross", "params": {"fast": 20, "slow": 80},
                                            "oos_fraction": 0.3})
    assert r.status_code == 200
    d = r.json()
    assert d["warnings"][0].startswith("ATENCIÓN") and d["segments"]["split_date"]
    assert client.post("/api/backtest", json={"symbol": "SPY", "strategy": "sma_cross", "params": {"fast": 90, "slow": 80}}).status_code == 422
    assert client.post("/api/backtest", json={"symbol": "SPY", "strategy": "magic"}).status_code == 422
    assert client.post("/api/backtest", json={"symbol": "SPY", "initial_capital": -5}).status_code == 422


def test_portfolio_average_cost_and_realized_pnl(client):
    pid = client.post("/api/portfolios", json={"name": "Manual", "base_currency": "USD"}).json()["id"]
    tx = lambda **k: client.post(f"/api/portfolios/{pid}/transactions", json=k)
    assert tx(type="deposit", amount=10_000).status_code == 201
    assert tx(type="buy", symbol="AAPL", quantity=10, price=100, fee=1).status_code == 201
    assert tx(type="buy", symbol="AAPL", quantity=10, price=120, fee=1).status_code == 201
    # coste medio = (1000+1 + 1200+1)/20 = 110.1
    assert tx(type="sell", symbol="AAPL", quantity=5, price=130, fee=1).status_code == 201
    s = client.get(f"/api/portfolios/{pid}").json()
    pos = s["positions"][0]
    assert pos["quantity"] == 15 and np.isclose(pos["avg_cost"], 110.1)
    assert np.isclose(s["realized_pnl"], (130 - 110.1) * 5 - 1)
    assert np.isclose(s["cash"], 10_000 - 1001 - 1201 + 650 - 1)
    assert s["warnings"] and "SINTÉTICOS" in s["warnings"][0]
    assert tx(type="sell", symbol="AAPL", quantity=99, price=1).status_code == 422   # no vender en corto
    assert tx(type="buy", symbol="AAPL", quantity=-1, price=1).status_code == 422
    assert tx(type="buy", symbol="XXXX", quantity=1, price=1).status_code == 422


def test_portfolio_foreign_currency_not_summed(client):
    pid = client.post("/api/portfolios", json={"name": "Mixta", "base_currency": "USD"}).json()["id"]
    client.post(f"/api/portfolios/{pid}/transactions", json={"type": "deposit", "amount": 1000})
    client.post(f"/api/portfolios/{pid}/transactions", json={"type": "buy", "symbol": "SAN", "quantity": 10, "price": 4})
    s = client.get(f"/api/portfolios/{pid}").json()
    assert s["invested_value"] == 0 and any("no se convierten" in w for w in s["warnings"])


def test_paper_trading_flow(client):
    pid = client.post("/api/portfolios", json={"name": "Paper", "paper": True}).json()["id"]
    assert client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 1}).status_code == 422  # sin efectivo
    client.post(f"/api/portfolios/{pid}/transactions", json={"type": "deposit", "amount": 100_000})
    r = client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 10})
    assert r.status_code == 201 and "[DATO SINTÉTICO]" in r.json()["note"] and r.json()["fee"] > 0
    s = client.get(f"/api/portfolios/{pid}").json()
    assert s["positions"][0]["quantity"] == 10 and s["cash"] < 100_000
    manual = client.post("/api/portfolios", json={"name": "M"}).json()["id"]
    assert client.post(f"/api/portfolios/{manual}/paper-order", json={"symbol": "AAPL", "side": "buy", "quantity": 1}).status_code == 422
    assert client.post(f"/api/portfolios/{pid}/paper-order", json={"symbol": "SAN", "side": "buy", "quantity": 1}).status_code == 422  # EUR vs USD


def test_export_import_roundtrip(client):
    pid = client.post("/api/portfolios", json={"name": "A"}).json()["id"]
    client.post(f"/api/portfolios/{pid}/transactions", json={"type": "deposit", "amount": 500})
    client.post(f"/api/portfolios/{pid}/transactions", json={"type": "buy", "symbol": "MSFT", "quantity": 2, "price": 100})
    csv_text = client.get(f"/api/portfolios/{pid}/export.csv").text
    pid2 = client.post("/api/portfolios", json={"name": "B"}).json()["id"]
    res = client.post(f"/api/portfolios/{pid2}/import", content=csv_text, headers={"content-type": "text/csv"}).json()
    assert res["imported"] == 2 and not res["errors"]
    assert client.get(f"/api/portfolios/{pid2}").json()["positions"][0]["quantity"] == 2
    bad = client.post(f"/api/portfolios/{pid2}/import", content="type,symbol\nfoo,AAPL\n", headers={"content-type": "text/csv"}).json()
    assert bad["imported"] == 0 and bad["errors"]


def test_portfolio_delete_and_404(client):
    pid = client.post("/api/portfolios", json={"name": "X"}).json()["id"]
    assert client.delete(f"/api/portfolios/{pid}").status_code == 200
    assert client.get(f"/api/portfolios/{pid}").status_code == 404


def test_auth_token(settings, monkeypatch):
    monkeypatch.setattr("openmarket.providers.base.time.sleep", lambda s: None)
    c = TestClient(create_app(replace(settings, api_token="s3cret")))
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/modules").status_code == 401
    assert c.get("/api/modules", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/modules", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_offline_mode_never_calls_network(settings, monkeypatch):
    import httpx

    from openmarket.providers import base
    base.set_transport(httpx.MockTransport(lambda r: pytest.fail("no debe haber red en modo offline")))
    c = TestClient(create_app(replace(settings, offline=True)))
    d = c.get("/api/assets/AAPL?validate=false").json()
    assert d["provenance"]["status"] == "synthetic"


def test_spa_serving_and_path_traversal(settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>OM</html>")
    (dist / "secret.txt").write_text("fuera")
    (tmp_path / "outside.txt").write_text("no")
    c = TestClient(create_app(replace(settings, frontend_dist=str(dist))))
    assert "OM" in c.get("/mercado/stock").text            # ruta de la SPA
    assert c.get("/secret.txt").text == "fuera"
    assert "OM" in c.get("/..%2foutside.txt").text          # traversal → index, nunca el archivo externo
    assert c.get("/api/nope").status_code == 404


def test_without_frontend_build_root_explains_instead_of_404(client):
    r = client.get("/")
    assert r.status_code == 200 and "falta la interfaz" in r.text and "/api/docs" in r.text
    assert client.get("/api/health").status_code == 200
