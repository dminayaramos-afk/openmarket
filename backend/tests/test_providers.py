import httpx
import pytest

from openmarket.models import ProviderError, clean_frame
from openmarket.providers import base as provider_base
from openmarket.providers.frankfurter import parse_frankfurter
from openmarket.providers.kraken import parse_kraken
from openmarket.providers.stooq import parse_stooq_csv

STOOQ = "Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,1000\n2024-01-03,10.5,12,10,11,1500\n"


def test_parse_stooq_ok_and_errors():
    df = clean_frame(parse_stooq_csv(STOOQ))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"] and len(df) == 2
    assert str(df.index.tz) == "UTC"
    with pytest.raises(ProviderError):
        parse_stooq_csv("No data")
    with pytest.raises(ProviderError):
        parse_stooq_csv("")


def test_parse_frankfurter_close_only():
    df = clean_frame(parse_frankfurter({"rates": {"2024-01-02": {"USD": 1.09}, "2024-01-03": {"USD": 1.1}}}, "USD"))
    assert (df["open"] == df["close"]).all() and df["volume"].sum() == 0
    with pytest.raises(ProviderError):
        parse_frankfurter({"rates": {}}, "USD")


def test_parse_kraken():
    payload = {"error": [], "result": {"XXBTZUSD": [[1704153600, "1", "2", "0.5", "1.5", "1.2", "10", 5],
                                                    [1704240000, "1.5", "2.5", "1", "2", "1.8", "12", 6]], "last": 1}}
    df = clean_frame(parse_kraken(payload))
    assert len(df) == 2 and df["close"].iloc[-1] == 2.0
    with pytest.raises(ProviderError):
        parse_kraken({"error": ["EQuery:Unknown asset pair"], "result": {}})


def test_service_uses_real_provider_then_cache(client):
    calls = []

    def handler(request: httpx.Request):
        calls.append(str(request.url))
        return httpx.Response(200, text=STOOQ)

    provider_base.set_transport(httpx.MockTransport(handler))
    r = client.get("/api/assets/AAPL?validate=false").json()
    assert r["provenance"]["provider"] == "Stooq" and r["provenance"]["status"] == "delayed"
    n = len(calls)
    client.get("/api/assets/AAPL?validate=false")
    assert len(calls) == n  # segunda petición servida desde la caché


def test_provider_failure_falls_back_to_labeled_synthetic(client):
    r = client.get("/api/assets/MSFT?validate=false").json()
    assert r["provenance"]["status"] == "synthetic" and r["provenance"]["status_label"] == "sintético"
    assert any("sintéticos" in w.lower() for w in r["provenance"]["warnings"])
    src = {s["name"]: s for s in client.get("/api/sources").json()["sources"]}
    assert src["stooq"]["error_count"] >= 1 and src["stooq"]["last_error"]


def test_no_fallback_returns_503(settings, monkeypatch):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from openmarket.main import create_app
    monkeypatch.setattr("openmarket.providers.base.time.sleep", lambda s: None)
    c = TestClient(create_app(replace(settings, demo_fallback=False)))
    assert c.get("/api/assets/AAPL").status_code == 503


def test_stale_cache_preferred_over_synthetic(client, monkeypatch):
    provider_base.set_transport(httpx.MockTransport(lambda r: httpx.Response(200, text=STOOQ)))
    client.get("/api/assets/AAPL?validate=false")
    provider_base.set_transport(httpx.MockTransport(lambda r: httpx.Response(500)))
    monkeypatch.setattr("openmarket.service.CACHE_TTL_SECONDS", -1)
    r = client.get("/api/assets/AAPL?validate=false").json()
    assert r["provenance"]["status"] == "delayed"
    assert any("caducada" in w.lower() for w in r["provenance"]["warnings"])


def test_retries_on_server_error(client):
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(500) if attempts["n"] < 3 else httpx.Response(200, text=STOOQ)

    provider_base.set_transport(httpx.MockTransport(handler))
    r = client.get("/api/assets/NVDA?validate=false").json()
    assert attempts["n"] == 3 and r["provenance"]["status"] == "delayed"


def test_circuit_breaker_opens_and_skips_calls(client):
    import httpx
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("caído")

    provider_base.set_transport(httpx.MockTransport(handler))
    client.get("/api/assets/AAPL?validate=false")
    after_first = calls["n"]
    assert after_first == 3                      # 3 intentos y se abre el cortacircuitos
    r = client.get("/api/assets/MSFT?validate=false").json()
    assert calls["n"] == after_first             # sin nuevas llamadas mientras está en pausa
    assert r["provenance"]["status"] == "synthetic"
    assert any("en pausa" in w for w in r["provenance"]["warnings"])


def test_client_errors_do_not_trip_breaker(client):
    import httpx
    provider_base.set_transport(httpx.MockTransport(lambda r: httpx.Response(404)))
    for sym in ("AAPL", "MSFT", "NVDA", "AMZN"):
        client.get(f"/api/assets/{sym}?validate=false")
    src = {s["name"]: s for s in client.get("/api/sources").json()["sources"]}
    assert src["stooq"]["error_count"] == 4 and "en pausa" not in (src["stooq"]["last_error"] or "")


def test_stooq_without_key_makes_no_request_and_explains(settings, monkeypatch):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from openmarket.main import create_app
    monkeypatch.setattr("openmarket.providers.base.time.sleep", lambda s: None)
    provider_base.set_transport(httpx.MockTransport(lambda r: pytest.fail("no debe haber petición sin clave")))
    c = TestClient(create_app(replace(settings, stooq_apikey="")))
    d = c.get("/api/assets/AAPL?validate=false").json()
    assert d["provenance"]["status"] == "synthetic"
    src = {s["name"]: s for s in c.get("/api/sources").json()["sources"]}
    assert "clave API" in src["stooq"]["last_error"] and "OPENMARKET_STOOQ_APIKEY" in src["stooq"]["last_error"]


def test_stooq_html_key_page_is_detected():
    with pytest.raises(ProviderError, match="clave API"):
        parse_stooq_csv("<!DOCTYPE html><html><body>Get your apikey</body></html>")


def test_stooq_sends_key_param(client):
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, text=STOOQ)

    provider_base.set_transport(httpx.MockTransport(handler))
    client.get("/api/assets/AAPL?validate=false")
    assert seen.get("apikey") == "clave-de-prueba" and seen.get("s") == "aapl.us"
