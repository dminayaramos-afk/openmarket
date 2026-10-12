"""`python -m openmarket` — arranca el servidor en 127.0.0.1 por defecto."""
import os

import uvicorn

from .config import load_settings

if __name__ == "__main__":
    load_settings()  # carga .env
    host = os.environ.get("OPENMARKET_HOST", "127.0.0.1")
    port = int(os.environ.get("OPENMARKET_PORT", "8000"))
    if host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("OPENMARKET_API_TOKEN"):
        raise SystemExit(
            "Rechazado: escuchar fuera de localhost exige OPENMARKET_API_TOKEN (y HTTPS delante). Ver SECURITY.md."
        )
    uvicorn.run("openmarket.main:app", host=host, port=port)
