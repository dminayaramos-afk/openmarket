# Contribuir a OpenMarket

1. Abre un *issue* antes de cambios grandes.
2. Backend: `cd backend && ../.venv/bin/python -m pytest -q` debe pasar. Añade pruebas para toda lógica numérica o de datos.
3. Frontend: `cd frontend && npm run typecheck && npm test`.
4. Reglas de oro del proyecto:
   - **Nunca** presentes datos sintéticos como reales, ni inventes precios, noticias o probabilidades.
   - Todo indicador debe ser **causal** (el valor en *t* no puede usar datos posteriores); hay una prueba que lo comprueba.
   - Una probabilidad solo se muestra si hay muestra suficiente y está validada fuera de muestra.
   - Las secciones no implementadas se marcan como tal, no se simulan.
   - Respeta licencias y condiciones de uso de los proveedores; sin *scraping* que las infrinja.
5. Nuevo proveedor: hereda de `Provider` (`backend/openmarket/providers/base.py`), implementa `fetch_daily`, regístralo en `service.py` y añade pruebas con respuestas simuladas.
6. Licencia: tu contribución se publica bajo AGPL-3.0-or-later.
