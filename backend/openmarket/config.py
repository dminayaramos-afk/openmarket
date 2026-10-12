"""Configuración por variables de entorno (sin dependencias externas)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/openmarket.db"
    api_token: str = ""
    demo_fallback: bool = True
    offline: bool = False
    stooq_url: str = "https://stooq.com"
    stooq_apikey: str = ""
    frankfurter_url: str = "https://api.frankfurter.dev/v1"
    kraken_url: str = "https://api.kraken.com"
    slippage_bps: float = 5.0
    commission_bps: float = 10.0
    cors_origins: tuple[str, ...] = field(default_factory=lambda: ("http://localhost:5173", "http://127.0.0.1:5173"))
    frontend_dist: str = ""
    csv_dir: str = "data/prices"


def _load_dotenv() -> None:
    """Carga un .env sencillo si existe (sin sobrescribir variables ya definidas)."""
    for candidate in (Path(".env"), Path(__file__).resolve().parents[2] / ".env"):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
            return


def load_settings() -> Settings:
    _load_dotenv()
    root = Path(__file__).resolve().parents[2]
    dist = os.environ.get("OPENMARKET_FRONTEND_DIST") or str(root / "frontend" / "dist")
    db = os.environ.get("OPENMARKET_DB", "data/openmarket.db")
    if not os.path.isabs(db):
        db = str(root / db)
    csv_dir = os.environ.get("OPENMARKET_CSV_DIR", "data/prices")
    if not os.path.isabs(csv_dir):
        csv_dir = str(root / csv_dir)
    cors = os.environ.get("OPENMARKET_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return Settings(
        db_path=db,
        api_token=os.environ.get("OPENMARKET_API_TOKEN", ""),
        demo_fallback=_bool("OPENMARKET_DEMO_FALLBACK", True),
        offline=_bool("OPENMARKET_OFFLINE", False),
        stooq_url=os.environ.get("OPENMARKET_STOOQ_URL", "https://stooq.com").rstrip("/"),
        stooq_apikey=os.environ.get("OPENMARKET_STOOQ_APIKEY", ""),
        frankfurter_url=os.environ.get("OPENMARKET_FRANKFURTER_URL", "https://api.frankfurter.dev/v1").rstrip("/"),
        kraken_url=os.environ.get("OPENMARKET_KRAKEN_URL", "https://api.kraken.com").rstrip("/"),
        slippage_bps=_float("OPENMARKET_SLIPPAGE_BPS", 5.0),
        commission_bps=_float("OPENMARKET_COMMISSION_BPS", 10.0),
        cors_origins=tuple(o.strip() for o in cors.split(",") if o.strip()),
        frontend_dist=dist,
        csv_dir=csv_dir,
    )
