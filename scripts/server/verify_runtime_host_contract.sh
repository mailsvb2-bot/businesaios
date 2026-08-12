#!/usr/bin/env bash
set -Eeuo pipefail

LOCAL_API_BASE="${LOCAL_API_BASE:-http://127.0.0.1:8000}"
LOCAL_WORKER_BASE="${LOCAL_WORKER_BASE:-http://127.0.0.1:8087}"
PUBLIC_API_BASE="${PUBLIC_API_BASE:-https://api.businessaios.ru}"
PUBLIC_STATUS_BASE="${PUBLIC_STATUS_BASE:-https://status.businessaios.ru}"
API_SERVICE="${API_SERVICE:-businesaios-api.service}"
WORKER_SERVICE="${WORKER_SERVICE:-businesaios-worker.service}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx.service}"

step() {
  printf '\n== %s ==\n' "$1"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

api_check() {
  local name="$1"
  local url="$2"
  echo "checking $name: $url"
  curl -fsS "$url" >/tmp/businesaios-api-health-check.json
  python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/businesaios-api-health-check.json').read_text())
status = str(payload.get('status') or '').lower()
if status not in {'ok', 'ready'}:
    raise SystemExit(f'api health status is not ok/ready: {status!r}')
failed = [item for item in payload.get('checks', []) if item.get('status') != 'pass']
if failed:
    raise SystemExit(f'failed api health checks: {failed!r}')
print('api health ok')
PY
}

worker_check() {
  local name="$1"
  local url="$2"
  echo "checking $name: $url"
  curl -fsS "$url" >/tmp/businesaios-worker-health-check.json
  python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/businesaios-worker-health-check.json').read_text())
if payload.get('ok') is not True:
    raise SystemExit(f'worker health is not ok: {payload!r}')
print('worker health ok')
PY
}

require_cmd curl
require_cmd python
require_cmd systemctl
require_cmd nginx

step "service state"
systemctl is-active --quiet "$API_SERVICE"
systemctl is-active --quiet "$WORKER_SERVICE"
systemctl is-active --quiet "$NGINX_SERVICE"

step "nginx syntax"
nginx -t

step "local core health"
api_check local-api "$LOCAL_API_BASE/health"
api_check local-api-ready "$LOCAL_API_BASE/readyz"
worker_check local-worker "$LOCAL_WORKER_BASE/health"
worker_check local-worker-ready "$LOCAL_WORKER_BASE/ready"

step "public api health"
api_check public-api "$PUBLIC_API_BASE/health"
api_check public-api-ready "$PUBLIC_API_BASE/readyz"

step "public status health"
api_check public-status "$PUBLIC_STATUS_BASE/health"

step "runtime host contract passed"
