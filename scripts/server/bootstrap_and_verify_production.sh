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
TELEGRAM_SERVICE="businesaios-connector-telegram.service"
PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"
BOOTSTRAP="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/bootstrap_production_control_plane.py"
VERIFY="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/verify_runtime_host_contract.sh"
LOCAL_HEALTH_URL="http://127.0.0.1:8000/health"
LOCAL_READINESS_URL="http://127.0.0.1:8000/readyz"
LOCAL_WORKER_HEALTH_URL="http://127.0.0.1:8087/health"
LOCAL_WORKER_READINESS_URL="http://127.0.0.1:8087/ready"
LOCAL_TELEGRAM_READINESS_URL="http://127.0.0.1:8088/readyz"
RUNTIME_USER="businesaios"
RUNTIME_GROUP="businesaios"
RUNTIME_API_DIR="/var/lib/businesaios/runtime/api"

fail() { echo "$*" >&2; exit 1; }

[[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "production bootstrap must run as root"
[[ "${EXPECTED_SHA:-}" =~ ^[0-9a-fA-F]{40}$ ]] || fail "EXPECTED_SHA must be a full 40-character git SHA"
EXPECTED_SHA="${EXPECTED_SHA,,}"
SMOKE_TENANT="${SMOKE_TENANT_ID:-}"
[[ -n "${SMOKE_TENANT//[[:space:]]/}" ]] || fail "SMOKE_TENANT_ID must name an existing production tenant"
[[ "$SMOKE_TENANT" != "default-business" ]] || fail "SMOKE_TENANT_ID must not use the unsafe default tenant"
APPROVED_PRICING_VERSION="${PRICING_VERSION:-}"
[[ -n "${APPROVED_PRICING_VERSION//[[:space:]]/}" ]] || fail "PRICING_VERSION must be an explicitly approved production pricing version"
# Do not let ambient shell values become a second runtime configuration source.
# The bootstrap receives the approved value as an explicit argument and writes
# it atomically into the sole production environment file.
unset SMOKE_TENANT_ID PRICING_VERSION

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

# Fail before credential/environment mutation when immutable production runtime
# bindings or tenant ownership have drifted. Production runtime is a consumer
# of an already-provisioned active tenant and policy bundle; it is never the
# authority that creates either one during startup.
echo "== canonical production runtime preflight =="
"$PYTHON_BIN" - "$PRODUCTION_ENV_FILE" "$SMOKE_TENANT" <<'PY'
from __future__ import annotations

import ipaddress
import sys
from pathlib import Path
from urllib.parse import urlsplit

from scripts.server.bootstrap_production_control_plane import (
    activated_environment,
    canonicalize_production_runtime_bindings,
    read_environment_file,
)
from tenancy.tenant_policy_store import PersistentTenantPolicyStore, build_default_tenant_policy_store
from tenancy.tenant_registry import PersistentTenantRegistry, build_default_tenant_registry

_, raw_values = read_environment_file(Path(sys.argv[1]))
try:
    values = canonicalize_production_runtime_bindings(raw_values)
except RuntimeError as exc:
    raise SystemExit(str(exc)) from exc
smoke_tenant = sys.argv[2].strip()

app_env = values.get("APP_ENV", "").strip().lower()
if app_env not in {"prod", "production"}:
    raise SystemExit("APP_ENV must be prod/production before credential bootstrap")

strict_mode = values.get("PRODUCTION_STRICT_MODE", "").strip().lower()
if strict_mode not in {"1", "true", "yes", "on"}:
    raise SystemExit("PRODUCTION_STRICT_MODE must be enabled in canonical production")

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
    "DATA_DIR": "/var/lib/businesaios/runtime",
}
for name, expected in required_exact.items():
    actual = values.get(name, "").strip()
    if actual != expected:
        raise SystemExit(f"{name} must be {expected!r} in canonical production (got {actual!r})")

if values.get("EVOLUTION_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
    raise SystemExit("EVOLUTION_ENABLED must be enabled in canonical production")

if not (values.get("DATABASE_URL", "").strip() or values.get("POSTGRES_DSN", "").strip()):
    raise SystemExit("DATABASE_URL/POSTGRES_DSN must be present before credential bootstrap")

fingerprint_path = Path(values.get("PRICING_FINGERPRINT_PATH", "").strip())
if not fingerprint_path.is_absolute():
    raise SystemExit("PRICING_FINGERPRINT_PATH must be absolute in canonical production")
runtime_root = Path("/var/lib/businesaios/runtime")
try:
    fingerprint_path.relative_to(runtime_root)
except ValueError as exc:
    raise SystemExit("PRICING_FINGERPRINT_PATH must live under the canonical runtime StateDirectory") from exc

if values.get("BUSINESAIOS_TENANT_POLICY_STORE_BACKEND", "file").strip().lower() != "file":
    raise SystemExit("production tenant policy store must use file backend")

with activated_environment(values):
    registry = build_default_tenant_registry()
    policy_store = build_default_tenant_policy_store()
if not isinstance(registry, PersistentTenantRegistry) or not registry.path.is_absolute():
    raise SystemExit("canonical production tenant registry must be persistent and absolute")
if not isinstance(policy_store, PersistentTenantPolicyStore) or not policy_store.path.is_absolute():
    raise SystemExit("canonical production tenant policy store must be persistent and absolute")
registry.assert_active(smoke_tenant)
policy_store.require(smoke_tenant)
PY

TELEGRAM_ENABLED=0
if systemctl is-enabled --quiet "$TELEGRAM_SERVICE" 2>/dev/null; then
  TELEGRAM_ENABLED=1
fi

# The host must be using effective service definitions shipped by the exact
# deployed SHA. Reject stale manager state and every undeclared or modified
# drop-in; release-declared byte-identical optional profiles remain part of the
# same SHA-bound systemd contract rather than hidden host-only configuration.
SERVICES=("$API_SERVICE" "$WORKER_SERVICE")
if [[ "$TELEGRAM_ENABLED" == "1" ]]; then
  SERVICES+=("$TELEGRAM_SERVICE")
fi
for service in "${SERVICES[@]}"; do
  need_reload="$(systemctl show "$service" -p NeedDaemonReload --value)"
  [[ "$need_reload" == "no" ]] || fail "systemd manager state is stale for $service; run systemctl daemon-reload before production bootstrap"
  drop_ins="$(systemctl show "$service" -p DropInPaths --value)"
  if [[ -n "${drop_ins//[[:space:]]/}" ]]; then
    read -r -a drop_in_paths <<< "$drop_ins"
    for drop_in in "${drop_in_paths[@]}"; do
      [[ -f "$drop_in" ]] || fail "installed systemd drop-in is missing for $service: $drop_in"
      drop_in_name="$(basename "$drop_in")"
      canonical_drop_in="$BUSINESAIOS_DEPLOY_ROOT/deploy/systemd/dropins/${service}.d/${drop_in_name}"
      [[ -f "$canonical_drop_in" ]] || fail "unexpected systemd drop-in for $service: $drop_in"
      cmp -s "$canonical_drop_in" "$drop_in" || fail "installed systemd drop-in does not match deployed SHA for $service: $drop_in"
    done
  fi
  fragment="$(systemctl show "$service" -p FragmentPath --value)"
  [[ -n "$fragment" && -f "$fragment" ]] || fail "installed systemd unit is missing for $service"
  canonical="$BUSINESAIOS_DEPLOY_ROOT/deploy/systemd/$service"
  [[ -f "$canonical" ]] || fail "deployed canonical systemd unit is missing: $canonical"
  cmp -s "$canonical" "$fragment" || fail "installed systemd unit does not match deployed SHA for $service; run deploy/systemd/install.sh before production bootstrap"
done

echo "== canonical production control-plane + pricing bootstrap =="
"$PYTHON_BIN" "$BOOTSTRAP" \
  --tenant-id "$SMOKE_TENANT" \
  --pricing-version "$APPROVED_PRICING_VERSION"

# The root-only bootstrap atomically rotates the persistent API-key store.
# Hand the resulting files back to the unprivileged runtime account before
# any service restart; otherwise root-owned replacement files fail closed.
install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" -m 0750 "$RUNTIME_API_DIR"
chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$RUNTIME_API_DIR"
chmod -R u+rwX,g+rX,o-rwx "$RUNTIME_API_DIR"
runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_API_DIR/api_keys.json" \
  || fail "runtime user cannot read canonical API-key store after bootstrap"
runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_API_DIR/api_keys.json" \
  || fail "runtime user cannot write canonical API-key store after bootstrap"

echo "== reload runtime with the newly bound production environment =="
if [[ "$TELEGRAM_ENABLED" == "1" ]]; then
  # Clear a previous start-limit-hit only for the already-enabled canonical
  # connector, then restart it in the same environment cutover as core runtime.
  systemctl reset-failed "$TELEGRAM_SERVICE" || true
  systemctl restart "$API_SERVICE" "$WORKER_SERVICE" "$TELEGRAM_SERVICE"
else
  systemctl restart "$API_SERVICE" "$WORKER_SERVICE"
fi

# systemd can report active before HTTP applications and health surfaces are
# ready. Enforce one 60-second wall-clock deadline around the complete runtime
# readiness loop; sequential per-probe timeouts must never multiply the rollout
# deadline. The historical API_READY name is retained as part of the existing
# host-lifecycle contract; success now represents core plus any enabled canonical
# connector participating in this same readiness gate.
if ! timeout 60s bash -c '
API_SERVICE="$1"
WORKER_SERVICE="$2"
TELEGRAM_SERVICE="$3"
TELEGRAM_ENABLED="$4"
LOCAL_HEALTH_URL="$5"
LOCAL_READINESS_URL="$6"
LOCAL_WORKER_HEALTH_URL="$7"
LOCAL_WORKER_READINESS_URL="$8"
LOCAL_TELEGRAM_READINESS_URL="$9"
API_READY=0
for ((attempt=1; attempt<=60; attempt++)); do
  core_ready=0
  telegram_ready=1
  if systemctl is-active --quiet "$API_SERVICE" \
    && systemctl is-active --quiet "$WORKER_SERVICE" \
    && curl -fsS --max-time 2 "$LOCAL_HEALTH_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_READINESS_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_WORKER_HEALTH_URL" >/dev/null \
    && curl -fsS --max-time 2 "$LOCAL_WORKER_READINESS_URL" >/dev/null; then
    core_ready=1
  fi
  if [[ "$TELEGRAM_ENABLED" == "1" ]]; then
    telegram_ready=0
    if systemctl is-active --quiet "$TELEGRAM_SERVICE" \
      && curl -fsS --max-time 2 "$LOCAL_TELEGRAM_READINESS_URL" >/dev/null; then
      telegram_ready=1
    fi
  fi
  if [[ "$core_ready" == "1" && "$telegram_ready" == "1" ]]; then
    API_READY=1
    break
  fi
  sleep 1
done
[[ "$API_READY" == "1" ]]
' _ "$API_SERVICE" "$WORKER_SERVICE" "$TELEGRAM_SERVICE" "$TELEGRAM_ENABLED" "$LOCAL_HEALTH_URL" "$LOCAL_READINESS_URL" "$LOCAL_WORKER_HEALTH_URL" "$LOCAL_WORKER_READINESS_URL" "$LOCAL_TELEGRAM_READINESS_URL"; then
  fail "runtime did not become healthy and ready within 60 seconds after restart: ${SERVICES[*]}"
fi

echo "== SHA-bound authenticated synthetic production verdict =="
EXPECTED_SHA="$EXPECTED_SHA" \
PRODUCTION_ENV_FILE="$PRODUCTION_ENV_FILE" \
BUSINESAIOS_DEPLOY_ROOT="$BUSINESAIOS_DEPLOY_ROOT" \
"$VERIFY"
