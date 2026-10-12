# Changelog

## 0.2.0 — 2026-10-12
- **Precio en vivo**: Kraken Ticker (cripto, sin clave) y Finnhub `/quote` (acciones/ETF de EE. UU., clave opcional `OPENMARKET_FINNHUB_KEY`). Caché de segundos, etiqueta «tiempo real», nunca se inventa un valor. `GET /api/live`; la ficha de activo se actualiza sola cada 10 s. El formato de Finnhub **no está verificado** contra el servicio real.
- **Diagnóstico de proveedores en la app**: `POST /api/diagnostics` y botón en Configuración (además de `python -m openmarket.check`). Caché diaria más corta para cripto (15 min) y forex (1 h).
- **Conversión de divisas en carteras** con tipos de referencia del BCE (Frankfurter), con aviso y sin inventar tipos.
- **Buscador de oportunidades** (`/api/screener`), **alertas** (`/api/alerts`, evaluadas con la app abierta, sin datos sintéticos), **calculadoras** de opciones (Black-Scholes, griegas, volatilidad implícita) y bonos (precio, YTM, duración, convexidad).
- Correcciones: la interfaz ya no se desborda en móvil (Dashboard); Stooq/Frankfurter usan fecha UTC.
- Verificación: 93 pruebas de backend, 18 de frontend, lint limpio, `pip-audit` y `npm audit` sin vulnerabilidades, y recorrido en Chromium real (escritorio y móvil) sin errores de JavaScript.

## 0.1.1 — 2026-10-12
- **Proveedor CSV local**: históricos propios en `data/prices/<SÍMBOLO>.csv` (datos reales sin red ni clave), con prioridad sobre la red; formato flexible (`,`/`;`, cabeceras en español/inglés, fechas ISO o dd/mm/aaaa, decimales con punto o coma).
- **Arranque sin Node.js**: el repositorio incluye `frontend/dist`; `scripts/start.sh` reescrito (Python ≥ 3.10, aviso de `python3-venv`, dependencias solo si cambian, comprobación de puerto, compila solo si falta `dist` y hay Node). `scripts/verify.sh` hace lint, pruebas y, si hay Node, el frontend.
- Página de ayuda en `/` cuando falta el frontend (en vez de un 404).
- Stooq: clave API obligatoria explicada en la app (sin clave no se intenta la descarga); comando `python -m openmarket.check` para probar los proveedores en vivo.
- Verificado con Python 3.10 + pandas 2.3 y con Python 3.13 + pandas 3. 70 pruebas de backend.

## 0.1.0 — 2026-10-12
- Backend FastAPI: catálogo de 40 activos, proveedores Stooq/Kraken/Frankfurter con caché SQLite, reintentos, límite de frecuencia y cortacircuitos; datos sintéticos etiquetados como respaldo.
- Indicadores (SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, VWAP, momentum), soportes/resistencias, riesgo histórico, correlaciones.
- Señal BAJISTA/NEUTRAL/ALCISTA con probabilidades empíricas y validación walk-forward (Brier, log loss).
- Carteras manuales y paper trading con coste medio, importación/exportación CSV.
- Backtesting sin información futura, con comisión, slippage y tramo fuera de muestra.
- Frontend React + TypeScript + Tailwind: dashboard, mercados, ficha de activo, carteras, backtesting, configuración; tema oscuro/claro.
- Token de acceso opcional, cabeceras de seguridad, negativa a escuchar fuera de localhost sin token.
