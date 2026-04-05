#!/bin/sh
set -eu

HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"
RELOAD="${APP_RELOAD:-false}"

mkdir -p /app/media

python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

database_url = os.environ["DATABASE_URL"].strip()

# Normalize bare postgres:// or postgresql:// to use the psycopg3 driver
# explicitly, matching the same logic in backend/db.py.
lower = database_url.lower()
if lower.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif lower.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]

for attempt in range(30):
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
PY

if [ "$RELOAD" = "true" ]; then
  exec uvicorn backend.main:app --host "$HOST" --port "$PORT" --reload --reload-dir /app/backend
fi

exec uvicorn backend.main:app --host "$HOST" --port "$PORT"
