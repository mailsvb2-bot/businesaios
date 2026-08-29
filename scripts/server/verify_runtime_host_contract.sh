#!/usr/bin/env bash
set -Eeuo pipefail

LOCAL_API_BASE="${LOCAL_API_BASE:-http://127.0.0.1:8000}"
LOCAL_WORKER_BASE="${LOCAL_WORKER_BASE:-http://127.0.0.1:8087}"
PUBLIC_STATUS_BASE="${PUBLIC_STATUS_BASE:-https://status.businessaios.ru}"
PUBLIC_APP_BASE="https://app.businessaios.ru"
API_SERVICE="${API_SERVICE:-businesaios-api.service}"
WORKER_SERVICE="${WORKER_SERVICE:-businesaios-worker.service}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx.service}"
BUSINESAIOS_DEPLOY_ROOT="${BUSINESAIOS_DEPLOY_ROOT:-/opt/businesaios}"
PRODUCTION_ENV_FILE="${PRODUCTION_ENV_FILE:-/etc/businesaios/api.env}"
PRODUCTION_VERDICT_DIR="${PRODUCTION_VERDICT_DIR:-/var/lib/businesaios/runtime/reports/post-deploy}"
PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"
export LOCAL_WORKER_BASE BUSINESAIOS_DEPLOY_ROOT

step() { printf '\n== %s ==\n' "$1"; }
fail() { echo "$*" >&2; return 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"; }
require_env() {
  local name="$1" value="${!1:-}"
  [[ -n "${value//[[:space:]]/}" ]] || fail "required production setting is missing: $name"
}

EXPECTED_SHA="${EXPECTED_SHA:-}"
[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "EXPECTED_SHA must be a full 40-character git SHA" >&2
  exit 1
}
EXPECTED_SHA="${EXPECTED_SHA,,}"
PRODUCTION_VERDICT_PATH="${PRODUCTION_VERDICT_PATH:-$PRODUCTION_VERDICT_DIR/production-verdict-$EXPECTED_SHA.json}"
CURRENT_CHECK="canonical_python"
PASSED_CHECKS=""
OBSERVED_SHA=""
SMOKE_JSON="{}"

[[ -x "$PYTHON_BIN" ]] || {
  echo "canonical production Python is missing or not executable: $PYTHON_BIN" >&2
  exit 1
}

write_verdict() {
  local verdict="$1" error="${2:-}"
  VERDICT_STATUS="$verdict" VERDICT_ERROR="$error" CURRENT_CHECK="$CURRENT_CHECK" \
  PASSED_CHECKS="$PASSED_CHECKS" OBSERVED_SHA="$OBSERVED_SHA" SMOKE_JSON="$SMOKE_JSON" \
  EXPECTED_SHA="$EXPECTED_SHA" PRODUCTION_VERDICT_PATH="$PRODUCTION_VERDICT_PATH" \
  APP_ENV_VALUE="${APP_ENV:-}" SMOKE_TENANT_VALUE="${SMOKE_TENANT_ID:-}" "$PYTHON_BIN" - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

path = Path(os.environ["PRODUCTION_VERDICT_PATH"])
passed = [name for name in os.environ.get("PASSED_CHECKS", "").split(",") if name]
checks = {name: {"status": "pass"} for name in passed}
status = os.environ["VERDICT_STATUS"]
current = os.environ.get("CURRENT_CHECK", "")
error = os.environ.get("VERDICT_ERROR", "")
if status == "fail" and current and current not in checks:
    checks[current] = {"status": "fail", "error": error}
try:
    smoke = json.loads(os.environ.get("SMOKE_JSON") or "{}")
except json.JSONDecodeError:
    smoke = {}
payload = {
    "schema_version": 1,
    "verdict": status,
    "expected_sha": os.environ["EXPECTED_SHA"],
    "observed_sha": os.environ.get("OBSERVED_SHA") or None,
    "environment": os.environ.get("APP_ENV_VALUE") or None,
    "tenant_id": os.environ.get("SMOKE_TENANT_VALUE") or None,
    "synthetic_run_id": smoke.get("run_id"),
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "checks": checks,
}
if error:
    payload["error"] = error
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

on_error() {
  local rc=$?
  trap - ERR
  write_verdict fail "check=$CURRENT_CHECK rc=$rc line=${BASH_LINENO[0]} command=$BASH_COMMAND" || true
  exit "$rc"
}
trap on_error ERR
mark_pass() { PASSED_CHECKS+="$1,"; }
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_environment_file"
[[ -r "$PRODUCTION_ENV_FILE" ]] || fail "production environment file is missing or unreadable: $PRODUCTION_ENV_FILE"
# Production settings below must come only from the root-owned environment
# file, never from an ambient shell. EXPECTED_SHA remains deliberately external.
unset APP_ENV PUBLIC_BASE_URL BUSINESAIOS_TRUST_PROXY_HEADERS BUSINESAIOS_TRUSTED_PROXY_IPS
unset CONTROL_PLANE_API_KEY SMOKE_TENANT_ID DATABASE_URL POSTGRES_DSN
unset HEALTH_HOST WORKER_HEALTH_PORT EVOLUTION_HEALTH_PORT EVOLUTION_ENABLED SMOKE_BASE_URL
set -a
# shellcheck disable=SC1090
source "$PRODUCTION_ENV_FILE"
set +a
unset SMOKE_BASE_URL
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_environment"
require_env APP_ENV
[[ "${APP_ENV,,}" == "prod" || "${APP_ENV,,}" == "production" ]] || fail "APP_ENV must be prod/production"
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_ingress"
require_env PUBLIC_BASE_URL
PUBLIC_BASE_URL="${PUBLIC_BASE_URL%/}"
PUBLIC_BASE_URL_VALUE="$PUBLIC_BASE_URL" "$PYTHON_BIN" - <<'PY'
import os
from urllib.parse import urlsplit

raw = os.environ['PUBLIC_BASE_URL_VALUE'].strip()
parsed = urlsplit(raw)
if parsed.scheme.lower() != 'https' or not parsed.hostname:
    raise SystemExit('PUBLIC_BASE_URL must be an absolute HTTPS origin')
if parsed.username or parsed.password or parsed.query or parsed.fragment:
    raise SystemExit('PUBLIC_BASE_URL must be an HTTPS origin without credentials, query, or fragment')
if parsed.path not in {'', '/'}:
    raise SystemExit('PUBLIC_BASE_URL must not contain an application path')
PY
require_env BUSINESAIOS_TRUST_PROXY_HEADERS
case "${BUSINESAIOS_TRUST_PROXY_HEADERS,,}" in
  1|true|yes|on) ;;
  *) fail "BUSINESAIOS_TRUST_PROXY_HEADERS must be enabled for the canonical nginx TLS boundary" ;;
esac
require_env BUSINESAIOS_TRUSTED_PROXY_IPS
TRUSTED_PROXY_IPS_VALUE="$BUSINESAIOS_TRUSTED_PROXY_IPS" "$PYTHON_BIN" - <<'PY'
import ipaddress
import os

raw = os.environ['TRUSTED_PROXY_IPS_VALUE']
networks = set()
for item in raw.replace(';', ',').split(','):
    text = item.strip()
    if not text:
        continue
    try:
        networks.add(ipaddress.ip_network(text, strict=False))
    except ValueError as exc:
        raise SystemExit(f'invalid BUSINESAIOS_TRUSTED_PROXY_IPS entry: {text!r}') from exc
expected = {ipaddress.ip_network('127.0.0.1/32'), ipaddress.ip_network('::1/128')}
if networks != expected:
    raise SystemExit('BUSINESAIOS_TRUSTED_PROXY_IPS must trust only loopback nginx peers: 127.0.0.1/32,::1/128')
PY
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_runtime_bindings"
require_env HEALTH_HOST
[[ "$HEALTH_HOST" == "127.0.0.1" ]] || fail "HEALTH_HOST must be 127.0.0.1 in canonical production"
require_env WORKER_HEALTH_PORT
[[ "$WORKER_HEALTH_PORT" == "8087" ]] || fail "WORKER_HEALTH_PORT must be 8087 in canonical production"
require_env EVOLUTION_HEALTH_PORT
[[ "$EVOLUTION_HEALTH_PORT" == "8087" ]] || fail "EVOLUTION_HEALTH_PORT must be 8087 in canonical production"
require_env EVOLUTION_ENABLED
case "${EVOLUTION_ENABLED,,}" in
  1|true|yes|on) ;;
  *) fail "EVOLUTION_ENABLED must be enabled in canonical production" ;;
esac
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_credentials"
require_env CONTROL_PLANE_API_KEY
[[ "$CONTROL_PLANE_API_KEY" != "development-control-plane-key" ]] || fail "unsafe production CONTROL_PLANE_API_KEY"
require_env SMOKE_TENANT_ID
[[ "$SMOKE_TENANT_ID" != "default-business" ]] || fail "unsafe production SMOKE_TENANT_ID"
DATABASE_DSN="${DATABASE_URL:-${POSTGRES_DSN:-}}"
[[ -n "${DATABASE_DSN//[[:space:]]/}" ]] || fail "required production PostgreSQL DSN is missing: DATABASE_URL/POSTGRES_DSN"
mark_pass "$CURRENT_CHECK"

for cmd in curl git systemctl nginx; do require_cmd "$cmd"; done

api_check() {
  local url="$1" auth="${2:-0}"
  local args=(-fsS "$url")
  [[ "$auth" == "1" ]] && args=(-fsS -H "x-api-key: $CONTROL_PLANE_API_KEY" "$url")
  curl "${args[@]}" >/tmp/businesaios-api-health-check.json
  "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/businesaios-api-health-check.json').read_text())
status = str(payload.get('status') or '').lower()
if status not in {'ok', 'ready'}:
    raise SystemExit(f'api health status is not ok/ready: {status!r}')
failed = [item for item in payload.get('checks', []) if item.get('status') != 'pass']
if failed:
    raise SystemExit(f'failed api health checks: {failed!r}')
PY
}

worker_check() {
  curl -fsS "$1" >/tmp/businesaios-worker-health-check.json
  "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/businesaios-worker-health-check.json').read_text())
if payload.get('ok') is not True:
    raise SystemExit(f'worker health is not ok: {payload!r}')
PY
}

CURRENT_CHECK="deployed_sha"
step "deployed SHA"
OBSERVED_SHA="$(git -C "$BUSINESAIOS_DEPLOY_ROOT" rev-parse HEAD)"
OBSERVED_SHA="${OBSERVED_SHA,,}"
[[ "$OBSERVED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "invalid deployed git SHA: $OBSERVED_SHA"
mark_pass "$CURRENT_CHECK"
CURRENT_CHECK="sha_match"
[[ "$OBSERVED_SHA" == "$EXPECTED_SHA" ]] || fail "observed SHA $OBSERVED_SHA does not match expected SHA $EXPECTED_SHA"
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="service_state"
step "service state"
systemctl is-active --quiet "$API_SERVICE"
systemctl is-active --quiet "$WORKER_SERVICE"
systemctl is-active --quiet "$NGINX_SERVICE"
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="nginx"
step "nginx syntax"
nginx -t
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="health"
step "local core health"
api_check "$LOCAL_API_BASE/health" 1
mark_pass "$CURRENT_CHECK"
CURRENT_CHECK="readiness"
api_check "$LOCAL_API_BASE/readyz" 1
mark_pass "$CURRENT_CHECK"
CURRENT_CHECK="runtime"
curl -fsS -H "x-api-key: $CONTROL_PLANE_API_KEY" "$LOCAL_API_BASE/health" >/tmp/businesaios-runtime-health-check.json
"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/businesaios-runtime-health-check.json').read_text())
details = payload.get('details') if isinstance(payload.get('details'), dict) else {}
readiness = details.get('runtime_readiness') or payload.get('runtime_readiness')
if not isinstance(readiness, dict) or readiness.get('ready') is not True:
    raise SystemExit(f'runtime readiness is not true: {readiness!r}')
if (payload.get('runtime_orchestrator_present') if 'runtime_orchestrator_present' in payload else details.get('runtime_orchestrator_present')) is not True:
    raise SystemExit('runtime orchestrator is not present')
PY
worker_check "$LOCAL_WORKER_BASE/health"
worker_check "$LOCAL_WORKER_BASE/ready"
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="postgresql"
step "PostgreSQL"
DATABASE_DSN="$DATABASE_DSN" "$PYTHON_BIN" - <<'PY'
import os
import psycopg
with psycopg.connect(os.environ['DATABASE_DSN'], connect_timeout=10) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT 1')
        row = cur.fetchone()
if not row or int(row[0]) != 1:
    raise SystemExit(f'PostgreSQL SELECT 1 returned unexpected result: {row!r}')
PY
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="synthetic_flow"
step "unique synthetic production flow through canonical HTTPS ingress"
SMOKE_JSON="$(SMOKE_BASE_URL="$PUBLIC_BASE_URL" "$PYTHON_BIN" - <<'PY'
import json
from scripts.server.smoke_flow import run_smoke_flow
print(json.dumps(run_smoke_flow(), sort_keys=True))
PY
)"
SMOKE_JSON="$SMOKE_JSON" "$PYTHON_BIN" - <<'PY'
import json
import os
payload = json.loads(os.environ['SMOKE_JSON'])
for key in ('run_id', 'idempotency_key', 'action_id', 'offer_id', 'tenant_id'):
    if not payload.get(key):
        raise SystemExit(f'synthetic flow did not return {key}')
PY
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="public_api"
step "public api health"
api_check "$PUBLIC_BASE_URL/health"
api_check "$PUBLIC_BASE_URL/readyz"
mark_pass "$CURRENT_CHECK"
CURRENT_CHECK="public_status"
step "public status health"
api_check "$PUBLIC_STATUS_BASE/health"
mark_pass "$CURRENT_CHECK"
CURRENT_CHECK="public_app"
step "public product workspace"
curl -fsS "$PUBLIC_APP_BASE/" >/tmp/businesaios-public-app.html
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
html = Path('/tmp/businesaios-public-app.html').read_text(encoding='utf-8', errors='replace')
if 'id="root"' not in html or '/assets/' not in html:
    raise SystemExit('public product workspace did not return the expected frontend shell')
PY
mark_pass "$CURRENT_CHECK"

CURRENT_CHECK="production_verdict"
mark_pass "$CURRENT_CHECK"
write_verdict pass
trap - ERR
step "runtime host contract passed"
echo "PRODUCTION_POST_DEPLOY_VERIFICATION_PASSED sha=$EXPECTED_SHA verdict=$PRODUCTION_VERDICT_PATH"
