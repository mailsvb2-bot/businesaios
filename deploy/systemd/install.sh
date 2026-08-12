#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/businesaios}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SYSUSERS_DIR="${SYSUSERS_DIR:-/usr/lib/sysusers.d}"
SYSUSERS_FILE="${SYSUSERS_FILE:-${SYSUSERS_DIR}/businesaios.conf}"
STATE_DIR="${STATE_DIR:-${APP_DIR}/data/deployment}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/release_state.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RELEASE_TAG="${RELEASE_TAG:-$(cat "${APP_DIR}/RELEASE_TAG" 2>/dev/null || echo unknown)}"
DEPLOY_PROFILE="${DEPLOY_PROFILE:-systemd-multichannel}"
START_SERVICES="${START_SERVICES:-1}"
HEALTH_STATUS="${HEALTH_STATUS:-pending}"
ENABLE_TELEGRAM_CONNECTOR="${ENABLE_TELEGRAM_CONNECTOR:-0}"
RUNTIME_USER="${RUNTIME_USER:-businesaios}"
RUNTIME_GROUP="${RUNTIME_GROUP:-businesaios}"
RUNTIME_ACCESS_SENTINEL="${RUNTIME_ACCESS_SENTINEL:-${APP_DIR}/scripts/server/migrate_before_start.py}"

CORE_UNITS=(
  businesaios-api.service
  businesaios-worker.service
)
TELEGRAM_CONNECTOR_UNIT=businesaios-connector-telegram.service
LEGACY_UNITS=(
  businesaios-telegram.service
  businesaios-evolution.service
)
OPTIONAL_UNITS=()

if [[ "$ENABLE_TELEGRAM_CONNECTOR" == "1" ]]; then
  OPTIONAL_UNITS+=("$TELEGRAM_CONNECTOR_UNIT")
fi

DEPLOY_UNITS=("${CORE_UNITS[@]}" "${OPTIONAL_UNITS[@]}")
DEPLOY_UNITS_CSV="$(IFS=,; echo "${DEPLOY_UNITS[*]}")"

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    echo "[install] root privileges are required and sudo is unavailable" >&2
    exit 1
  fi
  sudo "$@"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "[install] required file missing: $path" >&2
    exit 1
  fi
}

ensure_runtime_access() {
  if ! command -v runuser >/dev/null 2>&1; then
    echo "[install] runuser is required to verify runtime-user access" >&2
    exit 1
  fi

  echo "[install] granting ${RUNTIME_USER}:${RUNTIME_GROUP} read/execute access to application tree"
  run_root chgrp -R "$RUNTIME_GROUP" "$APP_DIR"
  run_root chmod -R g+rX "$APP_DIR"

  if ! run_root runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"; then
    echo "[install] runtime user cannot execute Python: $PYTHON_BIN" >&2
    exit 1
  fi
  if ! run_root runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_ACCESS_SENTINEL"; then
    echo "[install] runtime user cannot read application code: $RUNTIME_ACCESS_SENTINEL" >&2
    exit 1
  fi
  echo "[install] runtime access verified"
}

write_state() {
  mkdir -p "$STATE_DIR"
  PYTHONPATH="$APP_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    STATE_FILE="$STATE_FILE" \
    RELEASE_TAG="$RELEASE_TAG" \
    HEALTH_STATUS="$HEALTH_STATUS" \
    DEPLOY_PROFILE="$DEPLOY_PROFILE" \
    DEPLOY_UNITS="$DEPLOY_UNITS_CSV" \
    SYSTEMD_DIR="$SYSTEMD_DIR" \
    APP_DIR="$APP_DIR" \
    ACTIVATION_STATUS="$1" \
    "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import os

from deployment.release_state_store import DeploymentStateStore

store = DeploymentStateStore(os.environ['STATE_FILE'])
current = store.load()
release_tag = os.environ['RELEASE_TAG'].strip() or None
units = tuple(item for item in os.environ['DEPLOY_UNITS'].split(',') if item)
store.update(
    active_release=release_tag,
    previous_release=current.active_release,
    activation_status=os.environ['ACTIVATION_STATUS'],
    rollback_candidate=current.active_release or current.rollback_candidate,
    last_successful_health=os.environ['HEALTH_STATUS'].strip() or current.last_successful_health,
    applied_profile=os.environ['DEPLOY_PROFILE'].strip() or current.applied_profile,
    metadata={
        **dict(current.metadata),
        'systemd_dir': os.environ['SYSTEMD_DIR'],
        'app_dir': os.environ['APP_DIR'],
        'core_services': ['businesaios-api.service', 'businesaios-worker.service'],
        'enabled_services': list(units),
        'messaging_model': 'provider_connectors',
    },
)
PY
}

for unit in "${DEPLOY_UNITS[@]}"; do
  require_file "${APP_DIR}/deploy/systemd/${unit}"
done
require_file "${APP_DIR}/deploy/systemd/businesaios.sysusers.conf"
require_file "${APP_DIR}/RELEASE_TAG"
require_file "$RUNTIME_ACCESS_SENTINEL"

echo "[install] provisioning system user"
run_root install -d -m 0755 "$SYSUSERS_DIR"
run_root install -m 0644 "${APP_DIR}/deploy/systemd/businesaios.sysusers.conf" "$SYSUSERS_FILE"
run_root systemd-sysusers "$SYSUSERS_FILE"

# Production releases may be checked out or unpacked by root under a strict
# umask (for example 0077). The services deliberately run as an unprivileged
# account, so normalize only group read/traverse/execute access before systemd
# attempts ExecStartPre/ExecStart. This keeps the application tree non-writable
# to the runtime user while making the deployment path independent of caller
# umask.
ensure_runtime_access

write_state installing

echo "[install] installing core platform units: ${CORE_UNITS[*]}"
for unit in "${DEPLOY_UNITS[@]}"; do
  run_root install -m 0644 "${APP_DIR}/deploy/systemd/${unit}" "${SYSTEMD_DIR}/${unit}"
done

echo "[install] reloading systemd"
run_root systemctl daemon-reload

echo "[install] enabling core platform services"
run_root systemctl enable "${CORE_UNITS[@]}"
if ((${#OPTIONAL_UNITS[@]})); then
  echo "[install] enabling optional connector services: ${OPTIONAL_UNITS[*]}"
  run_root systemctl enable "${OPTIONAL_UNITS[@]}"
else
  echo "[install] no polling/streaming connector units requested"
fi

if [[ "$START_SERVICES" == "1" ]]; then
  echo "[install] restarting core platform services"
  run_root systemctl restart "${CORE_UNITS[@]}"
  if ((${#OPTIONAL_UNITS[@]})); then
    run_root systemctl restart "${OPTIONAL_UNITS[@]}"
  fi
  HEALTH_STATUS="running"
  ACTIVATION_STATUS="active"
else
  echo "[install] START_SERVICES=0, skipping restart"
  HEALTH_STATUS="installed"
  ACTIVATION_STATUS="installed"
fi

# Historical deployments treated Telegram and Evolution as the complete
# platform. Disable those unit names only after the canonical services have
# been installed (and, by default, restarted) successfully.
for legacy_unit in "${LEGACY_UNITS[@]}"; do
  run_root systemctl disable --now "$legacy_unit" >/dev/null 2>&1 || true
  run_root rm -f "${SYSTEMD_DIR}/${legacy_unit}"
done
run_root systemctl daemon-reload

write_state "$ACTIVATION_STATUS"

echo "[install] deployment state written to ${STATE_FILE}"
echo "[install] core runtime: ${CORE_UNITS[*]}"
if ((${#OPTIONAL_UNITS[@]})); then
  echo "[install] optional connectors: ${OPTIONAL_UNITS[*]}"
fi
echo "[install] done"
