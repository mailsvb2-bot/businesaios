#!/usr/bin/env bash
set -Eeuo pipefail

# Production lifecycle surfaces are intentionally not configurable here.
# Tests exercise the Python bootstrap against temporary paths directly, while
# the canonical host entrypoint is bound to one deploy root, env file and API
# service so plaintext credentials cannot be redirected to another surface.
BUSINESAIOS_DEPLOY_ROOT="/opt/businesaios"
PRODUCTION_ENV_FILE="/etc/businesaios/api.env"
API_SERVICE="businesaios-api.service"
PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"
BOOTSTRAP="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/bootstrap_production_control_plane.py"
VERIFY="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/verify_runtime_host_contract.sh"
LOCAL_HEALTH_URL="http://127.0.0.1:8000/health"
LOCAL_READINESS_URL="http://127.0.0.1:8000/readyz"

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
command -v curl >/dev/null 2>&1 || fail "curl is required for API readiness verification"

# The repository is intentionally not installed as a second application copy.
# Pin the canonical deploy root as the sole project import root so both the
# path-invoked bootstrap and verifier work independently of the caller's cwd.
export PYTHONPATH="$BUSINESAIOS_DEPLOY_ROOT"
cd "$BUSINESAIOS_DEPLOY_ROOT"

OBSERVED_SHA="$(git rev-parse HEAD)"
OBSERVED_SHA="${OBSERVED_SHA,,}"
[[ "$OBSERVED_SHA" == "$EXPECTED_SHA" ]] || fail "refusing credential bootstrap: deployed SHA $OBSERVED_SHA != expected SHA $EXPECTED_SHA"

echo "== canonical production control-plane bootstrap =="
"$PYTHON_BIN" "$BOOTSTRAP" --tenant-id "$SMOKE_TENANT"

echo "== reload API with the newly issued application-side key record =="
systemctl restart "$API_SERVICE"

# systemd can report active before the HTTP application has completed runtime
# boot. Do not enter the synthetic verifier until both canonical local probes
# actually answer successfully. The bounded wait fails closed after 60 seconds.
API_READY=0
for ((attempt=1; attempt<=60; attempt++)); do
  if systemctl is-active --quiet "$API_SERVICE" \
    && curl -fsS --max-time 2 "$LOCAL_HEALTH_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_READINESS_URL" >/dev/null; then
    API_READY=1
    break
  fi
  sleep 1
done
[[ "$API_READY" == "1" ]] || fail "API service did not become healthy and ready after restart: $API_SERVICE"

echo "== SHA-bound authenticated synthetic production verdict =="
EXPECTED_SHA="$EXPECTED_SHA" \
PRODUCTION_ENV_FILE="$PRODUCTION_ENV_FILE" \
BUSINESAIOS_DEPLOY_ROOT="$BUSINESAIOS_DEPLOY_ROOT" \
"$VERIFY"
