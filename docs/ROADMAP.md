# Registro de tareas

## Hecho (v0.1)
- [x] Estructura, configuración por entorno, SQLite
- [x] Catálogo de 40 activos (acciones, ETF, cripto, forex, materias primas, índices)
- [x] Proveedores Stooq / Kraken / Frankfurter + sintético etiquetado
- [x] Indicadores, riesgo histórico, correlaciones, soportes/resistencias
- [x] Señal + probabilidades + validación walk-forward
- [x] Carteras, paper trading, CSV
- [x] Backtesting con comisión/slippage/tramo fuera de muestra
- [x] Frontend: dashboard, mercados, ficha, carteras, backtesting, configuración
- [x] Proveedor CSV local y arranque sin Node (v0.1.1)
- [x] Token de acceso, cabeceras de seguridad, pruebas (backend y frontend)

- [x] Precio en vivo (Kraken; Finnhub opcional), diagnóstico en la app (v0.2.0)
- [x] Conversión de divisas, buscador, alertas, calculadoras de bonos y opciones (v0.2.0)

## Pendiente (por prioridad)
1. **Verificar proveedores contra los servicios reales** y ajustar códigos de símbolo.
2. Verificar el formato de Finnhub y la clave de Stooq contra los servicios reales.
3. Análisis fundamental (necesita proveedor con licencia clara).
4. Noticias verificadas y calendario económico (fuentes con enlace y fecha).
5. Datos de mercado de bonos y curvas de tipos (FRED/BCE), cadenas de opciones.
6. Notificaciones de alertas en segundo plano; IA financiera opcional (con consentimiento explícito para enviar datos).
7. Walk-forward con reentrenamiento y régimen de mercado; comparación con más modelos base.
8. Migraciones formales, PostgreSQL, CSP/HSTS en la guía de despliegue, CI con `pip-audit`.
9. Comparación entre exchanges cripto; curva de futuros (contango/backwardation).
