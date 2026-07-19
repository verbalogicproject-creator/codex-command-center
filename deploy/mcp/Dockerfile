FROM python:3.12-slim

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

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn aria_memory.mcp_app:app --host 0.0.0.0 --port \"${PORT}\" --timeout-keep-alive 120"]
