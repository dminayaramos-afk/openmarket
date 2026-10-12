FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=web /web/dist frontend/dist
ENV OPENMARKET_HOST=0.0.0.0 OPENMARKET_DB=/data/openmarket.db
VOLUME /data
EXPOSE 8000
WORKDIR /app/backend
# Al escuchar en 0.0.0.0 se exige OPENMARKET_API_TOKEN (ver SECURITY.md)
CMD ["python", "-m", "openmarket"]
