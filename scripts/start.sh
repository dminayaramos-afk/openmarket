#!/usr/bin/env bash
# Instala lo necesario (solo Python) y arranca OpenMarket en http://127.0.0.1:8000
# Node.js NO es necesario: el repositorio incluye el frontend ya compilado (frontend/dist).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- Python >= 3.10 -------------------------------------------------------------------------
PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[[ -n "$PY" ]] || die "se necesita Python 3.10 o superior (python3 --version). En Debian/MX/Ubuntu: sudo apt install python3 python3-venv"

# --- entorno virtual --------------------------------------------------------------------------
if [[ ! -x .venv/bin/python ]]; then
  "$PY" -m venv .venv 2>/dev/null || die "no se pudo crear el entorno virtual. En Debian/MX/Ubuntu: sudo apt install python3-venv  (y vuelve a ejecutar)"
fi
STAMP=".venv/.requirements.sha"
WANT="$(sha256sum backend/requirements.txt | cut -d' ' -f1)"
if [[ ! -f "$STAMP" || "$(cat "$STAMP")" != "$WANT" ]]; then
  echo "Instalando dependencias de Python (la primera vez tarda un poco)…"
  .venv/bin/python -m pip install --quiet -r backend/requirements.txt || die "falló pip install (¿sin conexión a internet?)"
  echo "$WANT" > "$STAMP"
fi

# --- frontend: solo se compila si falta y hay Node ----------------------------------------------
if [[ ! -f frontend/dist/index.html ]]; then
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "Compilando el frontend (no se encontró frontend/dist)…"
    (cd frontend && npm ci && npm run build) || echo "AVISO: no se pudo compilar el frontend; la API arrancará sin interfaz."
  else
    echo "AVISO: no hay frontend/dist ni Node.js; la API arrancará sin interfaz (ver /api/docs)."
  fi
fi

# --- configuración ---------------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Creado .env desde .env.example (opcional: pon ahí tu clave de Stooq)."
fi

# --- puerto libre ------------------------------------------------------------------------------------
PORT="${OPENMARKET_PORT:-8000}"
if .venv/bin/python - "$PORT" <<'PYEOF'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
PYEOF
then :; else die "el puerto $PORT está ocupado. Usa otro: OPENMARKET_PORT=8010 ./scripts/start.sh"; fi

echo
echo "OpenMarket → http://127.0.0.1:${PORT}   (Ctrl+C para parar)"
echo "Comprobar proveedores de datos:  (cd backend && ../.venv/bin/python -m openmarket.check)"
echo
cd backend
exec ../.venv/bin/python -m openmarket
