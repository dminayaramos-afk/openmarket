#!/usr/bin/env bash
# Repite los controles de calidad. El frontend solo se comprueba si hay Node.js.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || { echo "Primero ejecuta ./scripts/start.sh (crea el entorno)"; exit 1; }
.venv/bin/python -m pip install --quiet -r backend/requirements-dev.txt
echo "== Backend: lint y pruebas =="
(cd backend && ../.venv/bin/ruff check . && ../.venv/bin/python -m pytest -q)
echo
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  echo "== Frontend: tipos, build y pruebas =="
  (cd frontend && { [[ -d node_modules/vite ]] || npm ci; } && npm run typecheck && npm run build && npm test)
else
  echo "== Frontend: omitido (Node.js no instalado) =="
fi
echo
echo "Verificación terminada."
