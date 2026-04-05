#!/bin/sh
set -eu

HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"
RELOAD="${APP_RELOAD:-false}"

mkdir -p /app/media

python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

DEFAULT_DATABASE_URL = "postgresql+psycopg://deckly:deckly@127.0.0.1:5432/deckly"
database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

if not database_url:
    print("ERROR: DATABASE_URL is not set and no default is available.", file=sys.stderr)
    sys.exit(1)

for attempt in range(30):
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        break
    except Exception as exc:
        if attempt == 29:
            print(f"ERROR: Could not connect to the database after 30 attempts: {exc}", file=sys.stderr)
            raise
        time.sleep(1)
PY

if [ "$RELOAD" = "true" ]; then
  exec uvicorn backend.main:app --host "$HOST" --port "$PORT" --reload --reload-dir /app/backend
fi

exec uvicorn backend.main:app --host "$HOST" --port "$PORT"
