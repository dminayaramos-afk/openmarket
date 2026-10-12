# Seguridad

## Modelo de amenazas
OpenMarket está pensado para uso **personal y local**. Por defecto escucha solo en `127.0.0.1`, sin autenticación, porque solo tu equipo puede alcanzarlo.

## Acceso remoto
1. Define `OPENMARKET_API_TOKEN` con un valor largo y aleatorio (`python3 -c "import secrets;print(secrets.token_urlsafe(32))"`). Todos los endpoints `/api/*` (salvo `/api/health`) exigen `Authorization: Bearer <token>`. La comparación es en tiempo constante.
2. Pon **HTTPS** delante (Caddy, nginx o Traefik con certificado). El token viaja en cabeceras: sin HTTPS puede ser interceptado.
3. Solo entonces fija `OPENMARKET_HOST=0.0.0.0` (o la IP deseada). El servidor se **niega a arrancar** fuera de localhost sin token.
4. Mejor aún: no lo expongas a Internet; usa una VPN (WireGuard/Tailscale).

La interfaz web guarda el token en el almacenamiento local del navegador (Configuración → Acceso a la API). El token no se cifra allí: no lo uses en equipos compartidos.

## Datos y secretos
- Sin telemetría. Las carteras no salen del equipo.
- Las claves de proveedores (opcionales) se leen del entorno/`.env`. `.env` y `data/*.db` están en `.gitignore`. No subas secretos a Git.
- Copias de seguridad: copia `data/openmarket.db` con la app parada (o usa `sqlite3 data/openmarket.db ".backup copia.db"`). Restaurar = sustituir el archivo.

## Protecciones implementadas
- Validación de entradas con Pydantic (rangos, longitudes, patrones); consultas SQL parametrizadas.
- Protección contra *path traversal* al servir el frontend (probada).
- Cabeceras `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- CORS restringido a los orígenes de desarrollo configurados.
- Importación CSV limitada a 5000 filas y 2 MB.

## Pendiente / limitaciones
- Sin limitación de tasa por cliente ni gestión de usuarios: un solo token compartido.
- Sin cabecera `Content-Security-Policy` ni HSTS (hazlo en el proxy inverso).
- No se ha auditado el código ni las dependencias (`pip-audit`, `npm audit`).

## Operaciones reales
No existen en esta versión. Cuando se añadan integraciones con brókeres estarán desactivadas por defecto, con confirmación explícita, límites de riesgo, auditoría y parada de emergencia.

## Reportar vulnerabilidades
Abre un aviso de seguridad privado en el repositorio o escribe al mantenedor. No publiques detalles hasta que haya corrección.

## Claves de proveedores y llamadas salientes (v0.2.0)

- Las claves (`OPENMARKET_STOOQ_APIKEY`, `OPENMARKET_FINNHUB_KEY`) se leen solo del entorno o de `.env` (ignorado por Git) y nunca se devuelven por la API ni se escriben en los registros de OpenMarket.
- Stooq y Finnhub reciben la clave **como parámetro de la URL** (así lo exige su API según lo que sabemos): puede quedar en los registros de tu proxy o cortafuegos. Usa claves gratuitas y revócalas si las compartes sin querer.
- Las únicas llamadas salientes son a los proveedores configurados (Stooq, Kraken, Frankfurter y, si defines clave, Finnhub). No hay telemetría. `OPENMARKET_OFFLINE=true` las desactiva todas.
- `POST /api/diagnostics` hace consultas reales a los proveedores y está limitado a una cada 10 s.
