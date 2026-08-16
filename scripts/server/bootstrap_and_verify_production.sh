#!/usr/bin/env bash
set -Eeuo pipefail

# Production lifecycle surfaces are intentionally not configurable here.
# Tests exercise the Python bootstrap against temporary paths directly, while
# the canonical host entrypoint is bound to one deploy root, env file and core
# services so plaintext credentials cannot be redirected to another surface.
BUSINESAIOS_DEPLOY_ROOT="/opt/businesaios"
PRODUCTION_ENV_FILE="/etc/businesaios/api.env"
API_SERVICE="businesaios-api.service"
WORKER_SERVICE="businesaios-worker.service"
PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"
BOOTSTRAP="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/bootstrap_production_control_plane.py"
VERIFY="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/verify_runtime_host_contract.sh"
LOCAL_HEALTH_URL="http://127.0.0.1:8000/health"
LOCAL_READINESS_URL="http://127.0.0.1:8000/readyz"
LOCAL_WORKER_HEALTH_URL="http://127.0.0.1:8087/health"
LOCAL_WORKER_READINESS_URL="http://127.0.0.1:8087/ready"

fail() { echo "$*" >&2; exit 1; }

[[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "production bootstrap must run as root"
[[ "${EXPECTED_SHA:-}" =~ ^[0-9a-fA-F]{40}$ ]] || fail "EXPECTED_SHA must be a full 40-character git SHA"
EXPECTED_SHA="${EXPECTED_SHA,,}"
SMOKE_TENANT="${SMOKE_TENANT_ID:-}"
[[ -n "${SMOKE_TENANT//[[:space:]]/}" ]] || fail "SMOKE_TENANT_ID must name an existing production tenant"
[[ "$SMOKE_TENANT" != "default-business" ]] || fail "SMOKE_TENANT_ID must not use the unsafe default tenant"
unset SMOKE_TENANT_ID

[[ -d "$BUSINESAIOS_DEPLOY_ROOT" ]] || fail "canonical production deploy root is missing: $BUSINESAIOS_DEPLOY_ROOT"
[[ -x "$PYTHON_BIN" ]] || fail "canonical production Python is missing: $PYTHON_BIN"
[[ -f "$BOOTSTRAP" ]] || fail "canonical production credential bootstrap is missing: $BOOTSTRAP"
[[ -x "$VERIFY" ]] || fail "canonical production verifier is missing or not executable: $VERIFY"
[[ -r "$PRODUCTION_ENV_FILE" ]] || fail "production environment file is missing or unreadable: $PRODUCTION_ENV_FILE"
command -v curl >/dev/null 2>&1 || fail "curl is required for runtime readiness verification"
command -v systemctl >/dev/null 2>&1 || fail "systemctl is required for production service verification"
command -v timeout >/dev/null 2>&1 || fail "timeout is required for the bounded runtime readiness deadline"

# The repository is intentionally not installed as a second application copy.
# Pin the canonical deploy root as the sole project import root so both the
# path-invoked bootstrap and verifier work independently of the caller's cwd.
export PYTHONPATH="$BUSINESAIOS_DEPLOY_ROOT"
cd "$BUSINESAIOS_DEPLOY_ROOT"

OBSERVED_SHA="$(git rev-parse HEAD)"
OBSERVED_SHA="${OBSERVED_SHA,,}"
[[ "$OBSERVED_SHA" == "$EXPECTED_SHA" ]] || fail "refusing credential bootstrap: deployed SHA $OBSERVED_SHA != expected SHA $EXPECTED_SHA"

# Fail before credential mutation when immutable production runtime bindings
# have drifted. In particular, the worker health surface is loopback-only on a
# systemd host; exposing port 8087 on 0.0.0.0 is not a valid production state.
echo "== canonical production runtime preflight =="
"$PYTHON_BIN" - "$PRODUCTION_ENV_FILE" <<'PY'
from __future__ import annotations

import ipaddress
import sys
from pathlib import Path
from urllib.parse import urlsplit

from scripts.server.bootstrap_production_control_plane import read_environment_file

_, values = read_environment_file(Path(sys.argv[1]))

app_env = values.get("APP_ENV", "").strip().lower()
if app_env not in {"prod", "production"}:
    raise SystemExit("APP_ENV must be prod/production before credential bootstrap")

public_base_url = values.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
parsed = urlsplit(public_base_url)
if parsed.scheme.lower() != "https" or not parsed.hostname:
    raise SystemExit("PUBLIC_BASE_URL must be an absolute HTTPS origin before credential bootstrap")
if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
    raise SystemExit("PUBLIC_BASE_URL must be an HTTPS origin without credentials, path, query, or fragment")

trust_proxy = values.get("BUSINESAIOS_TRUST_PROXY_HEADERS", "").strip().lower()
if trust_proxy not in {"1", "true", "yes", "on"}:
    raise SystemExit("BUSINESAIOS_TRUST_PROXY_HEADERS must be enabled before credential bootstrap")

networks = set()
for item in values.get("BUSINESAIOS_TRUSTED_PROXY_IPS", "").replace(";", ",").split(","):
    text = item.strip()
    if text:
        networks.add(ipaddress.ip_network(text, strict=False))
expected_networks = {
    ipaddress.ip_network("127.0.0.1/32"),
    ipaddress.ip_network("::1/128"),
}
if networks != expected_networks:
    raise SystemExit("BUSINESAIOS_TRUSTED_PROXY_IPS must trust only loopback nginx peers")

required_exact = {
    "HEALTH_HOST": "127.0.0.1",
    "WORKER_HEALTH_PORT": "8087",
    "EVOLUTION_HEALTH_PORT": "8087",
}
for name, expected in required_exact.items():
    actual = values.get(name, "").strip()
    if actual != expected:
        raise SystemExit(f"{name} must be {expected!r} in canonical production (got {actual!r})")

if values.get("EVOLUTION_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
    raise SystemExit("EVOLUTION_ENABLED must be enabled in canonical production")

if not (values.get("DATABASE_URL", "").strip() or values.get("POSTGRES_DSN", "").strip()):
    raise SystemExit("DATABASE_URL/POSTGRES_DSN must be present before credential bootstrap")
PY

# The host must be using the service definitions shipped by the exact deployed
# SHA. This is especially important for the worker unit because it provides a
# second loopback-only guard even if a future environment file drifts.
for service in "$API_SERVICE" "$WORKER_SERVICE"; do
  fragment="$(systemctl show "$service" -p FragmentPath --value)"
  [[ -n "$fragment" && -f "$fragment" ]] || fail "installed systemd unit is missing for $service"
  canonical="$BUSINESAIOS_DEPLOY_ROOT/deploy/systemd/$service"
  [[ -f "$canonical" ]] || fail "deployed canonical systemd unit is missing: $canonical"
  cmp -s "$canonical" "$fragment" || fail "installed systemd unit does not match deployed SHA for $service; run deploy/systemd/install.sh before production bootstrap"
done

echo "== canonical production control-plane bootstrap =="
"$PYTHON_BIN" "$BOOTSTRAP" --tenant-id "$SMOKE_TENANT"

echo "== reload core runtime with the newly deployed code and application-side key record =="
systemctl restart "$API_SERVICE" "$WORKER_SERVICE"

# systemd can report active before HTTP applications and worker health surfaces
# are ready. Enforce one 60-second wall-clock deadline around the complete core
# runtime readiness loop; sequential per-probe timeouts must never multiply the
# rollout deadline.
if ! timeout 60s bash -c '
API_SERVICE="$1"
WORKER_SERVICE="$2"
LOCAL_HEALTH_URL="$3"
LOCAL_READINESS_URL="$4"
LOCAL_WORKER_HEALTH_URL="$5"
LOCAL_WORKER_READINESS_URL="$6"
API_READY=0
for ((attempt=1; attempt<=60; attempt++)); do
  if systemctl is-active --quiet "$API_SERVICE" \
    && systemctl is-active --quiet "$WORKER_SERVICE" \
    && curl -fsS --max-time 2 "$LOCAL_HEALTH_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_READINESS_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_WORKER_HEALTH_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_WORKER_READINESS_URL" >/dev/null; then
    API_READY=1
    break
  fi
  sleep 1
done
[[ "$API_READY" == "1" ]]
' _ "$API_SERVICE" "$WORKER_SERVICE" "$LOCAL_HEALTH_URL" "$LOCAL_READINESS_URL" "$LOCAL_WORKER_HEALTH_URL" "$LOCAL_WORKER_READINESS_URL"; then
  fail "core runtime did not become healthy and ready within 60 seconds after restart: $API_SERVICE $WORKER_SERVICE"
fi

echo "== SHA-bound authenticated synthetic production verdict =="
EXPECTED_SHA="$EXPECTED_SHA" \
PRODUCTION_ENV_FILE="$PRODUCTION_ENV_FILE" \
BUSINESAIOS_DEPLOY_ROOT="$BUSINESAIOS_DEPLOY_ROOT" \
"$VERIFY"
