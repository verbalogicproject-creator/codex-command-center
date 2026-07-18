FROM node:22-bookworm-slim AS web
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=cloud \
    DATA_DIR=/tmp/command-center-v3 \
    PORT=8080
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY services/memory ./services/memory
RUN pip install --no-cache-dir ".[postgres]"
COPY fixtures ./fixtures
COPY --from=web /build/apps/web/out ./apps/web/out
EXPOSE 8080
CMD ["sh", "-c", "uvicorn aria_memory.app:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 120"]
