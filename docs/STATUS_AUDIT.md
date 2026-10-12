# Auditoría de entrega de OpenMarket

Fecha de auditoría: 2026-10-12. Auditoría del ZIP recibido; no implica verificación de servicios externos.

## Comprobado en este entorno

- Backend: `58 passed` con `python -m pytest -q`.
- El repositorio contiene frontend React/TypeScript, API FastAPI, SQLite, adaptadores Stooq/Kraken/Frankfurter, carteras, paper trading y backtesting.
- Se añadieron `scripts/start.sh` para instalación/compilación/arranque y `scripts/verify.sh` para repetir los controles.

## No verificado / bloqueos

- No se pudo completar la instalación limpia de dependencias npm en el entorno de auditoría. El intento de build terminó con `TS2688: Cannot find type definition file for 'vite/client'`, coherente con una instalación incompleta de `node_modules`; no es suficiente para atribuir el fallo al código fuente.
- No se pudieron confirmar llamadas a proveedores financieros en vivo. Ejecuta `cd backend && ../.venv/bin/python -m openmarket.check` desde una máquina con internet y credenciales válidas.
- No se validó Docker ni un arranque end-to-end con navegador.
- Bonos, derivados, IA financiera, alertas, noticias/calendario y análisis fundamental/macro siguen marcados como no implementados en el README/API.

## Cómo verificar en Linux

1. Instala Python 3.10+, Node.js 20+ y npm.
2. Ejecuta `./scripts/start.sh`. Esto instala dependencias, compila el frontend y arranca la API.
3. Abre `http://127.0.0.1:8000`.
4. En otra terminal, ejecuta `./scripts/verify.sh`.
5. Para comprobar fuentes externas, desde `backend/` ejecuta `../.venv/bin/python -m openmarket.check`.

No uses datos sintéticos como datos de mercado reales. Las señales y el backtesting son herramientas de estudio, no garantías de rentabilidad ni asesoramiento financiero.

## Seguimiento (v0.1.1)

- **Build de npm fallido en la auditoría**: ya no bloquea el uso. El repositorio incluye `frontend/dist` y `scripts/start.sh` no usa Node si `dist` existe. El fallo `TS2688` de la auditoría corresponde a una instalación incompleta de `node_modules`; con `npm ci` y conexión se resuelve (verificado en el desarrollo: typecheck, build y tests pasan).
- **Instalación limpia verificada**: copia limpia del repositorio, Python 3.10, sin Node en el PATH → `./scripts/start.sh` instala, arranca y sirve interfaz y API.
- **Compatibilidad**: 70 pruebas de backend pasan con Python 3.10 + pandas 2.3 y con Python 3.13 + pandas 3.
- **Sigue sin verificarse**: llamadas en vivo a Stooq, Kraken y Frankfurter (sin acceso de red en el entorno de desarrollo; ejecuta `python -m openmarket.check`), Docker y la interfaz en un navegador real.
- Nueva vía de datos reales sin red ni claves: CSV propios en `data/prices/`.
