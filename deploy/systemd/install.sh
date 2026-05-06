#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/businesaios}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
STATE_DIR="${STATE_DIR:-${APP_DIR}/data/deployment}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/release_state.json}"
TELEGRAM_UNIT="businesaios-telegram.service"
EVOLUTION_UNIT="businesaios-evolution.service"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RELEASE_TAG="${RELEASE_TAG:-$(cat "${APP_DIR}/RELEASE_TAG" 2>/dev/null || echo unknown)}"
DEPLOY_PROFILE="${DEPLOY_PROFILE:-systemd}"
START_SERVICES="${START_SERVICES:-1}"
HEALTH_STATUS="${HEALTH_STATUS:-pending}"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "[install] required file missing: $path" >&2
    exit 1
  fi
}

write_state() {
  mkdir -p "$STATE_DIR"
  PYTHONPATH="$APP_DIR${PYTHONPATH:+:$PYTHONPATH}" STATE_FILE="$STATE_FILE" RELEASE_TAG="$RELEASE_TAG" HEALTH_STATUS="$HEALTH_STATUS" DEPLOY_PROFILE="$DEPLOY_PROFILE" SYSTEMD_DIR="$SYSTEMD_DIR" APP_DIR="$APP_DIR" ACTIVATION_STATUS="$1" "$PYTHON_BIN" - <<'PY'
from __future__ import annotations
import os
from deployment.release_state_store import DeploymentStateStore

store = DeploymentStateStore(os.environ['STATE_FILE'])
current = store.load()
release_tag = os.environ['RELEASE_TAG'].strip() or None
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
    },
)
PY
}

require_file "${APP_DIR}/deploy/systemd/${TELEGRAM_UNIT}"
require_file "${APP_DIR}/deploy/systemd/${EVOLUTION_UNIT}"
require_file "${APP_DIR}/RELEASE_TAG"

write_state installing

echo "[install] copying unit files..."
sudo install -m 0644 "${APP_DIR}/deploy/systemd/${TELEGRAM_UNIT}" "${SYSTEMD_DIR}/${TELEGRAM_UNIT}"
sudo install -m 0644 "${APP_DIR}/deploy/systemd/${EVOLUTION_UNIT}" "${SYSTEMD_DIR}/${EVOLUTION_UNIT}"

echo "[install] reloading systemd..."
sudo systemctl daemon-reload

echo "[install] enabling services..."
sudo systemctl enable "$TELEGRAM_UNIT" "$EVOLUTION_UNIT"

if [[ "$START_SERVICES" == "1" ]]; then
  echo "[install] restarting services..."
  sudo systemctl restart "$TELEGRAM_UNIT" "$EVOLUTION_UNIT"
  HEALTH_STATUS="running"
  ACTIVATION_STATUS="active"
else
  echo "[install] START_SERVICES=0, skipping restart"
  HEALTH_STATUS="installed"
  ACTIVATION_STATUS="installed"
fi

write_state "$ACTIVATION_STATUS"

echo "[install] deployment state written to ${STATE_FILE}"
echo "[install] done."
