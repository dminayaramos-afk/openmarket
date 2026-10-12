# Arquitectura

```
frontend/ (React + TS + Tailwind + lightweight-charts)  ──/api──▶  backend/openmarket (FastAPI)
                                                                     ├─ catalog.py      activos y normalización de símbolos
                                                                     ├─ service.py      elige proveedor → caché → respaldo sintético
                                                                     ├─ providers/      csvfile · stooq · kraken · frankfurter · synthetic
                                                                     ├─ analysis/       indicators · signals · risk · backtest
                                                                     ├─ portfolio.py    carteras, coste medio, paper trading
                                                                     └─ db.py           SQLite (caché, carteras, favoritos)
```

## Flujo de datos
`get_series(symbol)`: **CSV local** (`data/prices/<SÍMBOLO>.csv`, prioridad máxima, sin caché) → caché fresca (6 h) → proveedor(es) del activo (reintentos con retroceso exponencial, límite de frecuencia, cortacircuitos tras 3 fallos de red/5xx) → caché caducada (con aviso) → datos sintéticos etiquetados (si `OPENMARKET_DEMO_FALLBACK`) → error 503.
Cada serie lleva su **procedencia** (proveedor, estado, fecha, avisos) hasta la interfaz.

## Decisiones
- **SQLite + WAL**: cero administración, suficiente para uso personal. PostgreSQL queda para instalaciones mayores (no implementado).
- **Un solo proceso sirve API y frontend compilado**: instalación simple, sin Node en producción.
- **Cálculo causal**: indicadores y señales usan solo datos ≤ t; pruebas lo verifican alterando el futuro.
- **Probabilidades**: frecuencias empíricas condicionadas al estado de señal, solo con ≥ 100 observaciones, usando únicamente resultados ya observables (t'+h ≤ t). Las ventanas se solapan: la muestra efectiva ≈ n/h, y se muestra.
- **Backtest**: señal al cierre de t → ejecución en la apertura de t+1 con slippage y comisión; no optimiza parámetros.
- **Wilder**: RSI/ATR/ADX usan el suavizado de Wilder sembrado con media simple (verificado contra una serie de referencia).

## Extender
Nuevo proveedor: subclase de `Provider`. Nuevo indicador: función causal en `analysis/indicators.py` + prueba de causalidad. Nueva estrategia: añadir a `STRATEGIES` y a `target_position`.
