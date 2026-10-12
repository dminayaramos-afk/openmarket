import httpx
import pytest

from openmarket.catalog import CATALOG
from openmarket.models import ProviderError
from openmarket.providers import base as provider_base
from openmarket.providers.csvfile import parse_csv

STOOQ_STYLE = "Date,Open,High,Low,Close,Volume\n" + "\n".join(
    f"2024-01-{d:02d},{10 + d * 0.1:.2f},{11 + d * 0.1:.2f},{9 + d * 0.1:.2f},{10.5 + d * 0.1:.2f},{1000 + d}" for d in range(1, 29)
)


def test_parse_english_iso():
    df = parse_csv(STOOQ_STYLE)
    assert len(df) == 28 and str(df.index.tz) == "UTC" and df["close"].iloc[0] == pytest.approx(10.6)


def test_parse_spanish_semicolon_decimal_comma_dayfirst():
    text = "Fecha;Apertura;Máximo;Mínimo;Cierre;Volumen\n02/01/2024;1.234,50;1.240,00;1.230,00;1.236,75;1.000\n03/01/2024;1.236,75;1.250,00;1.235,00;1.249,10;2.000\n"
    df = parse_csv(text)
    assert list(df.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]   # dd/mm, no mm/dd
    assert df["close"].tolist() == [1236.75, 1249.10] and df["volume"].tolist() == [1000, 2000]


def test_parse_close_only_and_adj_close():
    df = parse_csv("Date,Adj Close\n2024-01-02,10\n2024-01-03,11\n")
    assert (df["open"] == df["close"]).all()


@pytest.mark.parametrize("text,msg", [
    ("", "vacío"), ("Foo,Bar\n1,2\n", "fecha"), ("Date,Close\n2024-01-02,x\n2024-01-03,y\n", "al menos 2 filas"),
    ("Date,Close\n2024-01-02,-1\n2024-01-03,5\n", "≤ 0"),
])
def test_parse_rejects_bad_files(text, msg):
    with pytest.raises(ProviderError, match=msg):
        parse_csv(text)


def _write(settings, name, text):
    import pathlib
    d = pathlib.Path(settings.csv_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


def test_local_csv_has_priority_and_needs_no_network(client, settings):
    provider_base.set_transport(httpx.MockTransport(lambda r: pytest.fail("no debe usar la red si hay CSV")))
    _write(settings, "aapl.csv", STOOQ_STYLE)     # el nombre no distingue mayúsculas
    d = client.get("/api/assets/AAPL?validate=false").json()
    p = d["provenance"]
    assert p["provider"] == "Archivo CSV local" and p["status"] == "historical" and p["status_label"] == "histórico"
    assert "aportados por el usuario" in p["note"] and d["bars"] == 28
    q = client.get("/api/quotes?symbols=AAPL").json()
    assert q["any_synthetic"] is False


def test_bad_csv_is_reported_and_falls_back_to_labeled_synthetic(client, settings):
    _write(settings, "MSFT.csv", "esto,no,es\nun,csv,valido\n")
    d = client.get("/api/assets/MSFT?validate=false").json()
    assert d["provenance"]["status"] == "synthetic"
    assert any("CSV local ignorado" in w for w in d["provenance"]["warnings"])
    src = {s["name"]: s for s in client.get("/api/sources").json()["sources"]}
    assert src["csv"]["error_count"] == 1 and "fecha" in src["csv"]["last_error"]


def test_csv_source_listed_with_detected_files(client, settings):
    _write(settings, "BTC-USD.csv", STOOQ_STYLE)
    _write(settings, "desconocido.csv", STOOQ_STYLE)
    csv = {s["name"]: s for s in client.get("/api/sources").json()["sources"]}["csv"]
    assert "BTC-USD" in csv["description"] and "desconocido" not in csv["description"] and csv["enabled"]


def test_csv_file_name_cannot_escape_directory(client, settings, tmp_path):
    (tmp_path / "AAPL.csv").write_text(STOOQ_STYLE)       # fuera de la carpeta de precios
    _write(settings, "otro.csv", STOOQ_STYLE)
    d = client.get("/api/assets/AAPL?validate=false").json()
    assert d["provenance"]["status"] == "synthetic"        # el archivo de fuera no se lee
    assert client.get("/api/assets/..%2fAAPL").status_code in (404, 422)
    assert "AAPL" in CATALOG
