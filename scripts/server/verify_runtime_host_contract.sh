#!/usr/bin/env bash
set -Eeuo pipefail

LOCAL_API_BASE="${LOCAL_API_BASE:-http://127.0.0.1:8000}"
PUBLIC_API_BASE="${PUBLIC_API_BASE:-https://api.businessaios.ru}"
PUBLIC_STATUS_BASE="${PUBLIC_STATUS_BASE:-https://status.businessaios.ru}"
API_SERVICE="${API_SERVICE:-businesaios-api.service}"
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

health_check() {
  local name="$1"
  local url="$2"
  echo "checking $name: $url"
  curl -fsS "$url" >/tmp/businesaios-health-check.json
  python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/businesaios-health-check.json').read_text())
status = payload.get('status')
checks = payload.get('checks', [])
if status != 'ok':
    raise SystemExit(f'health status is not ok: {status!r}')
failed = [item for item in checks if item.get('status') != 'pass']
if failed:
    raise SystemExit(f'failed health checks: {failed!r}')
print('health ok')
PY
}

require_cmd curl
require_cmd python
require_cmd systemctl
require_cmd nginx

step "service state"
systemctl is-active --quiet "$API_SERVICE"
systemctl is-active --quiet "$NGINX_SERVICE"

step "nginx syntax"
nginx -t

step "local health"
health_check local "$LOCAL_API_BASE/healthz"

step "public api health"
health_check api "$PUBLIC_API_BASE/healthz"

step "public status health"
health_check status "$PUBLIC_STATUS_BASE/healthz"

step "runtime host contract passed"
