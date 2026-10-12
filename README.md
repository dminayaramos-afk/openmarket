<p align="center"><img src="docs/logo.png" alt="OpenMarket" width="96"></p>

# OpenMarket

Plataforma financiera **de código abierto, autoalojable y privada** para analizar mercados, estudiar riesgos y probar estrategias. Funciona en local, sin servidor central, sin telemetría y sin cuenta de bróker.

> **Estado: v0.1 (Fases A–C parciales, D y E mínimas).** Lee la sección [Qué funciona y qué no](#qué-funciona-y-qué-no) antes de usarla. Análisis informativo: no es asesoramiento financiero ni predice el mercado.

## Qué funciona y qué no

| Área | Estado |
|---|---|
| Dashboard, buscador universal, mapa de calor, correlaciones, estado de fuentes | Funciona |
| Ficha de activo: gráfico de velas interactivo, indicadores, riesgo histórico, soportes/resistencias | Funciona |
| Señal BAJISTA/NEUTRAL/ALCISTA + probabilidades empíricas + validación walk-forward | Funciona (experimental, ver más abajo) |
| Acciones, ETF, índices (Stooq) · Cripto (Kraken spot) · Forex (BCE/Frankfurter) · Materias primas (Stooq) | Código listo; **no verificado contra los servicios reales** (ver Limitaciones) |
| **Históricos propios en CSV (`data/prices/`)** | Funciona; probado de extremo a extremo con datos de prueba |
| Carteras manuales, paper trading, importación/exportación CSV | Funciona (sin conversión de divisas) |
| Backtesting (4 estrategias, comisiones, slippage, tramo fuera de muestra) | Funciona |
| Bonos, derivados, buscador de oportunidades, IA financiera, alertas, noticias, calendario, análisis fundamental/macro | **No implementado** (la interfaz lo indica como «pronto») |
| Operaciones reales con brókeres | **No existe, por diseño** |

### Antes de usarla con datos reales (2 minutos)

1. **Acciones, ETF, índices y materias primas necesitan una clave gratuita de Stooq** (desde marzo de 2026). Solicítala en <https://stooq.com/q/d/?s=spy.us&get_apikey> y ponla en `.env` como `OPENMARKET_STOOQ_APIKEY=...`. Sin clave, esos activos se muestran como **sintéticos** y la app te dice por qué. Cripto (Kraken) y forex (Frankfurter) no necesitan clave.
2. Comprueba los proveedores en vivo desde tu equipo:
   ```bash
   cd backend && ../.venv/bin/python -m openmarket.check
   ```
   Imprime `OK` o `FALLO` por proveedor con el motivo. Si algo falla, pega la salida en un *issue*.

### Limitaciones que debes conocer

1. **Los proveedores reales no se han probado en vivo** (y el nombre del parámetro de la clave de Stooq, `apikey`, no está verificado). El entorno de desarrollo no tenía acceso de red a Stooq, Kraken ni Frankfurter. Los adaptadores se prueban con respuestas simuladas (formato, errores, reintentos, caché, cortacircuitos). Si algún código de símbolo o formato no coincide con el servicio real, el error aparece en *Configuración → Fuentes de datos* y la app muestra datos **sintéticos claramente etiquetados**. Si lo ves, abre un *issue*.
2. **Las probabilidades no son una predicción.** Son frecuencias históricas del propio activo con el mismo estado de señal. La validación walk-forward las compara con la frecuencia incondicional; en los datos sintéticos de prueba **no la superan** (mejora ≈ 0,2 %), y la interfaz lo dice. No las uses para decidir.
3. Sin conversión de divisas: las posiciones en otra moneda no suman al total de la cartera.
4. Datos diarios con retraso; no hay tiempo real.
5. Cripto: un único exchange (Kraken). Forex: tipos de referencia, no ejecutables. Materias primas: futuros continuos con saltos de vencimiento.

## Inicio rápido (Linux)

Requisito: **Python ≥ 3.10**. Node.js **no** hace falta (el repositorio incluye el frontend ya compilado).

```bash
./scripts/start.sh        # crea .venv, instala dependencias y arranca
```

Abre <http://127.0.0.1:8000>. Para parar: `Ctrl+C`. Otro puerto: `OPENMARKET_PORT=8010 ./scripts/start.sh`.
En Debian/MX/Ubuntu, si falla la creación del entorno: `sudo apt install python3 python3-venv`.

Sin conexión o para probar la interfaz: `OPENMARKET_OFFLINE=true` (todo se mostrará como **sintético**).

### Usar datos reales sin red ni claves: CSV propios

Guarda un archivo por activo en `data/prices/` con el símbolo como nombre (`AAPL.csv`, `BTC-USD.csv`, `EURUSD.csv`…).
Tiene prioridad sobre cualquier proveedor de red y se marca como **histórico · Archivo CSV local**. Acepta las descargas
habituales (Stooq, Yahoo…): separador `,` o `;`, cabeceras en inglés o español, fechas ISO o dd/mm/aaaa, decimales con punto
o coma. Detalles en `data/prices/LEEME.txt`.

### Desarrollo

```bash
# Terminal 1 — API
cd backend && ../.venv/bin/python -m openmarket
# Terminal 2 — frontend con recarga en caliente (requiere Node.js ≥ 20; proxy a la API)
cd frontend && npm ci && npm run dev          # http://localhost:5173
# Tras cambiar el frontend, recompila y vuelve a incluir dist:  npm run build
```

Pruebas y calidad (repite todos los controles con `./scripts/verify.sh`):

```bash
cd backend && ../.venv/bin/python -m pytest -q      # backend (también probado con Python 3.10 + pandas 2.3)
cd frontend && npm run typecheck && npm test         # frontend
```

### Docker (opcional)

```bash
docker compose up --build            # http://127.0.0.1:8000
```

El `Dockerfile` y el `docker-compose.yml` están escritos pero **no se han podido ejecutar** en el entorno de desarrollo (sin Docker). Trátalos como no verificados.

## Datos, procedencia y honestidad

Cada precio muestra proveedor, fecha del dato, momento de la descarga y **estado**: `sintético`, `retrasado` o `histórico`. Los datos sintéticos nunca se presentan como reales: aparece un aviso en todas las pantallas que los usan y las órdenes de paper trading los marcan en su nota.

## Configuración

Todo por variables de entorno (ver [`.env.example`](.env.example)). Ninguna clave es obligatoria. Los proveedores gratuitos tienen sus propias condiciones de uso: revísalas antes de redistribuir datos.

## Privacidad y seguridad

Sin telemetría. Carteras y favoritos viven solo en `data/openmarket.db` (SQLite). El servidor solo escucha en `127.0.0.1` y **se niega a arrancar** en otra interfaz sin `OPENMARKET_API_TOKEN`. Ver [SECURITY.md](SECURITY.md).

## Arquitectura

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Registro de tareas: [docs/ROADMAP.md](docs/ROADMAP.md).

## Licencia

[AGPL-3.0-or-later](LICENSE). Las dependencias principales (FastAPI, pandas, NumPy, httpx, React, Vite, Tailwind, lightweight-charts) usan licencias permisivas (MIT/BSD/Apache-2.0) compatibles; comprueba las versiones concretas con `pip-licenses` / `license-checker` antes de distribuir.
