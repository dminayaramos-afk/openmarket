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

## Pendiente (por prioridad)
1. **Verificar proveedores contra los servicios reales** y ajustar códigos de símbolo.
2. Conversión de divisas en carteras (Frankfurter).
3. Análisis fundamental (necesita proveedor con licencia clara).
4. Noticias verificadas y calendario económico (fuentes con enlace y fecha).
5. Bonos y curvas de tipos (FRED/BCE), derivados, buscador de oportunidades.
6. Alertas; IA financiera opcional (con consentimiento explícito para enviar datos).
7. Walk-forward con reentrenamiento y régimen de mercado; comparación con más modelos base.
8. Migraciones formales, PostgreSQL, CSP/HSTS en la guía de despliegue, `pip-audit`.
9. Comparación entre exchanges cripto; curva de futuros (contango/backwardation).
