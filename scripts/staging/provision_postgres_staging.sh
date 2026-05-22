#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT_DIR"

DB_NAME="${BAIOS_STAGING_DB_NAME:-businesaios_staging}"
DB_USER="${BAIOS_STAGING_DB_USER:-businesaios_staging}"
DB_HOST="${BAIOS_STAGING_DB_HOST:-127.0.0.1}"
DB_PORT="${BAIOS_STAGING_DB_PORT:-5432}"
ENV_FILE="${BAIOS_STAGING_ENV_FILE:-.env.staging.local}"
PASSWORD="${BAIOS_STAGING_DB_PASSWORD:-}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ "$DB_NAME" =~ [^a-zA-Z0-9_] ]]; then
  echo "invalid DB_NAME: only letters, digits and underscore are allowed" >&2
  exit 2
fi
if [[ "$DB_USER" =~ [^a-zA-Z0-9_] ]]; then
  echo "invalid DB_USER: only letters, digits and underscore are allowed" >&2
  exit 2
fi
if [[ "$DB_PORT" =~ [^0-9] ]]; then
  echo "invalid DB_PORT: only digits are allowed" >&2
  exit 2
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PYTHON_BIN" >&2
  exit 2
fi

if [[ -z "$PASSWORD" ]]; then
  # URL-safe password alphabet to reduce operator friction. The final DSN is
  # still percent-encoded below, because externally supplied passwords can
  # contain URI-reserved characters.
  PASSWORD="$(openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | head -c 40)"
fi

sql_quote() {
  printf "%s" "$1" | sed "s/'/''/g"
}

url_quote() {
  local value="$1"
  "$PYTHON_BIN" -c 'from urllib.parse import quote; import sys; print(quote(sys.argv[1], safe=""))' "$value"
}

run_psql_as_postgres() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -u postgres psql -v ON_ERROR_STOP=1 "$@"
  else
    su - postgres -c "psql -v ON_ERROR_STOP=1 $*"
  fi
}

ROLE_EXISTS="$(run_psql_as_postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$(sql_quote "$DB_USER")';" | tr -d '[:space:]')"
if [[ "$ROLE_EXISTS" != "1" ]]; then
  run_psql_as_postgres -c "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$(sql_quote "$PASSWORD")';"
else
  run_psql_as_postgres -c "ALTER ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$(sql_quote "$PASSWORD")';"
fi

DB_EXISTS="$(run_psql_as_postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(sql_quote "$DB_NAME")';" | tr -d '[:space:]')"
if [[ "$DB_EXISTS" != "1" ]]; then
  run_psql_as_postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
else
  run_psql_as_postgres -c "ALTER DATABASE \"$DB_NAME\" OWNER TO \"$DB_USER\";"
fi

run_psql_as_postgres -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE \"$DB_NAME\" TO \"$DB_USER\";"
run_psql_as_postgres -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO \"$DB_USER\";"
run_psql_as_postgres -d "$DB_NAME" -c "ALTER SCHEMA public OWNER TO \"$DB_USER\";"

URL_USER="$(url_quote "$DB_USER")"
URL_PASSWORD="$(url_quote "$PASSWORD")"
URL_DB="$(url_quote "$DB_NAME")"
DATABASE_URL="postgresql://${URL_USER}:${URL_PASSWORD}@${DB_HOST}:${DB_PORT}/${URL_DB}"
{
  echo "# Local staging file. Do not commit."
  echo "DATABASE_URL='${DATABASE_URL}'"
  echo "POSTGRES_RUNTIME_ENABLED=1"
  echo "POSTGRES_EVENT_STORE_ENABLED=1"
  echo "POSTGRES_APPLY_MIGRATIONS=1"
  echo "RUN_MIGRATIONS_BEFORE_START=1"
  echo "STAGING_RUNTIME_PROOF_REQUIRED=1"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

PGPASSWORD="$PASSWORD" psql \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT 1;" >/dev/null

cat <<EOF
staging Postgres provisioned
  db_name=$DB_NAME
  db_user=$DB_USER
  db_host=$DB_HOST
  db_port=$DB_PORT
  env_file=$ENV_FILE

Next:
  set -a
  source $ENV_FILE
  set +a
  bash scripts/staging/run_staging_runtime_proof.sh
EOF
