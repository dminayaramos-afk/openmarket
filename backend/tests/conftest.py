import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from openmarket.config import Settings
from openmarket.main import create_app
from openmarket.providers import base as provider_base


@pytest.fixture(autouse=True)
def _no_network():
    """Ninguna prueba toca la red real: transporte HTTP simulado que falla salvo que se sustituya."""
    import httpx

    def refuse(request):
        raise httpx.ConnectError("sin red en pruebas")

    provider_base.set_transport(httpx.MockTransport(refuse))
    yield
    provider_base.set_transport(None)


@pytest.fixture()
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "t.db"), stooq_apikey="clave-de-prueba", csv_dir=str(tmp_path / "prices"), demo_fallback=True, offline=False, frontend_dist=str(tmp_path / "nodist"))


@pytest.fixture()
def client(settings, monkeypatch):
    # Reintentos sin esperas en pruebas
    monkeypatch.setattr("openmarket.providers.base.time.sleep", lambda s: None)
    return TestClient(create_app(settings))


def make_ohlc(n=600, seed=1, drift=0.0004, vol=0.01, start="2022-01-03"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start=start, periods=n, tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0}, index=idx)


@pytest.fixture()
def ohlc():
    return make_ohlc()
