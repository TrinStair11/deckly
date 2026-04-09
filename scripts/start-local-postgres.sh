#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DATA_DIR="$ROOT_DIR/.local/postgres"
LOG_FILE="$ROOT_DIR/.local/postgres.log"
SOCKET_DIR="$ROOT_DIR/.local/postgres-socket"
BIN_DIR="/usr/lib/postgresql/14/bin"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

POSTGRES_DB="${POSTGRES_DB:-deckly}"
POSTGRES_USER="${POSTGRES_USER:-deckly}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-deckly}"

mkdir -p "$ROOT_DIR/.local"
mkdir -p "$SOCKET_DIR"
chmod 700 "$SOCKET_DIR"

if [[ ! -f "$DATA_DIR/PG_VERSION" ]]; then
  PWFILE="$ROOT_DIR/.local/postgres.pw"
  umask 077
  printf '%s\n' "$POSTGRES_PASSWORD" > "$PWFILE"
  "$BIN_DIR/initdb" \
    --auth-local=trust \
    --auth-host=scram-sha-256 \
    --username="$POSTGRES_USER" \
    --pwfile="$PWFILE" \
    -D "$DATA_DIR" >/dev/null
  rm -f "$PWFILE"
fi

if ! "$BIN_DIR/pg_ctl" -D "$DATA_DIR" status >/dev/null 2>&1; then
  "$BIN_DIR/pg_ctl" -D "$DATA_DIR" -l "$LOG_FILE" -o "-c listen_addresses='' -k '$SOCKET_DIR'" start >/dev/null
fi

if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$SOCKET_DIR" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'select 1' >/dev/null 2>&1; then
  PGPASSWORD="$POSTGRES_PASSWORD" createdb -h "$SOCKET_DIR" -U "$POSTGRES_USER" "$POSTGRES_DB"
fi

printf 'Local PostgreSQL is ready on socket %s\n' "$SOCKET_DIR"
