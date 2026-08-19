#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/businesaios}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SYSUSERS_DIR="${SYSUSERS_DIR:-/usr/lib/sysusers.d}"
SYSUSERS_FILE="${SYSUSERS_FILE:-${SYSUSERS_DIR}/businesaios.conf}"
STATE_DIR="${STATE_DIR:-${APP_DIR}/data/deployment}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/release_state.json}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"
RELEASE_TAG="${RELEASE_TAG:-$(cat "${APP_DIR}/RELEASE_TAG" 2>/dev/null || echo unknown)}"
DEPLOY_PROFILE="${DEPLOY_PROFILE:-systemd-multichannel}"
START_SERVICES="${START_SERVICES:-1}"
HEALTH_STATUS="${HEALTH_STATUS:-pending}"
ENABLE_TELEGRAM_CONNECTOR="${ENABLE_TELEGRAM_CONNECTOR:-0}"
RUNTIME_USER="${RUNTIME_USER:-businesaios}"
RUNTIME_GROUP="${RUNTIME_GROUP:-businesaios}"
RUNTIME_ACCESS_SENTINEL="${RUNTIME_ACCESS_SENTINEL:-${APP_DIR}/scripts/server/migrate_before_start.py}"
RUNTIME_DATA_DIR="${RUNTIME_DATA_DIR:-/var/lib/businesaios/runtime}"
LEGACY_SECURITY_DIR="${LEGACY_SECURITY_DIR:-${APP_DIR}/data/security}"
RUNTIME_SECURITY_DIR="${RUNTIME_SECURITY_DIR:-${RUNTIME_DATA_DIR}/security}"
RUNTIME_TENANCY_DIR="${RUNTIME_TENANCY_DIR:-${RUNTIME_DATA_DIR}/tenancy}"

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
  run_root chmod -R g-w "$APP_DIR"
  run_root chmod -R g+rX "$APP_DIR"

  if [[ -n "$(run_root find "$APP_DIR" \( -type f -o -type d \) -perm -g=w -print -quit)" ]]; then
    echo "[install] application tree still contains group-writable files or directories" >&2
    exit 1
  fi
  if ! run_root runuser -u "$RUNTIME_USER" -- test -x "$PYTHON_BIN"; then
    echo "[install] runtime user cannot execute Python: $PYTHON_BIN" >&2
    exit 1
  fi
  if ! run_root runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_ACCESS_SENTINEL"; then
    echo "[install] runtime user cannot read application code: $RUNTIME_ACCESS_SENTINEL" >&2
    exit 1
  fi
  if run_root runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_ACCESS_SENTINEL"; then
    echo "[install] runtime user must not be able to modify application code: $RUNTIME_ACCESS_SENTINEL" >&2
    exit 1
  fi
  echo "[install] runtime access verified"
}

verify_legacy_security_lineage() {
  run_root env \
    LEGACY_SECURITY_DIR="$LEGACY_SECURITY_DIR" \
    RUNTIME_SECURITY_DIR="$RUNTIME_SECURITY_DIR" \
    "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import filecmp
import json
import os
import sys
from pathlib import Path

legacy = Path(os.environ["LEGACY_SECURITY_DIR"])
runtime = Path(os.environ["RUNTIME_SECURITY_DIR"])

approved_backups = {
    "key_provider.json": (
        "key_provider.json.legacy-secret-b64.bak",
        "key_provider.json.pre-inline-vault-keys.bak",
    ),
    "secret_vault.json": (
        "secret_vault.json.legacy-inline-keys.bak",
    ),
}


def _migrated_shape_is_valid(relative: str, current: Path) -> bool:
    try:
        payload = json.loads(current.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False

    if relative == "key_provider.json":
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            return False
        if not all(isinstance(item, dict) for item in records):
            return False
        wrapped = all(
            str(item.get("key_envelope_version") or "").strip() == "BAIOS-KE2"
            and bool(str(item.get("wrapped_secret") or "").strip())
            and not bool(str(item.get("secret_b64") or "").strip())
            for item in records
        )
        migration_marker = isinstance(payload.get("migration"), dict) or isinstance(
            payload.get("inline_vault_key_migration"), dict
        )
        return wrapped and migration_marker

    if relative == "secret_vault.json":
        records = payload.get("records")
        if not isinstance(records, list):
            return False
        if payload.get("keys"):
            return False
        return (
            payload.get("key_storage") == "external_key_provider"
            and isinstance(payload.get("inline_key_migration"), dict)
        )

    return False


legacy_files = sorted(path for path in legacy.rglob("*") if path.is_file())
if not legacy_files:
    print("[install] legacy security directory contains no files")
    raise SystemExit(0)

for source in legacy_files:
    relative = source.relative_to(legacy).as_posix()
    current = runtime / relative
    if current.is_file() and filecmp.cmp(source, current, shallow=False):
        continue

    backup_names = approved_backups.get(relative, ())
    matching_backup = next(
        (
            runtime / name
            for name in backup_names
            if (runtime / name).is_file()
            and filecmp.cmp(source, runtime / name, shallow=False)
        ),
        None,
    )
    if matching_backup is None or not current.is_file() or not _migrated_shape_is_valid(relative, current):
        print(
            f"[install] unverified divergent legacy security file: {relative}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(
        "[install] verified migrated security successor "
        f"{relative} via rollback source {matching_backup.name}"
    )

print("[install] divergent runtime security state has verified migration lineage")
PY
}

migrate_legacy_security_state() {
  local legacy_present=0
  local runtime_present=0

  run_root install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" -m 0750 "$RUNTIME_DATA_DIR"
  run_root install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" -m 0750 "$RUNTIME_SECURITY_DIR"
  run_root install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" -m 0750 "$RUNTIME_TENANCY_DIR"

  if [[ -d "$LEGACY_SECURITY_DIR" ]] && [[ -n "$(find "$LEGACY_SECURITY_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    legacy_present=1
  fi
  if [[ -n "$(find "$RUNTIME_SECURITY_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    runtime_present=1
  fi

  if [[ "$legacy_present" == "1" ]]; then
    if [[ "$runtime_present" == "1" ]]; then
      if diff -qr "$LEGACY_SECURITY_DIR" "$RUNTIME_SECURITY_DIR" >/dev/null; then
        echo "[install] runtime security state already matches legacy source"
      elif verify_legacy_security_lineage; then
        echo "[install] preserving verified migrated runtime security state"
      else
        echo "[install] refusing to overwrite divergent runtime security state without verified migration lineage" >&2
        echo "[install] legacy=${LEGACY_SECURITY_DIR}" >&2
        echo "[install] runtime=${RUNTIME_SECURITY_DIR}" >&2
        exit 1
      fi
    else
      echo "[install] migrating legacy security state to writable runtime directory"
      run_root cp -a "$LEGACY_SECURITY_DIR/." "$RUNTIME_SECURITY_DIR/"
      if ! diff -qr "$LEGACY_SECURITY_DIR" "$RUNTIME_SECURITY_DIR" >/dev/null; then
        echo "[install] security-state copy verification failed" >&2
        exit 1
      fi
      echo "[install] legacy security source preserved at ${LEGACY_SECURITY_DIR}"
    fi
  fi

  run_root chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$RUNTIME_SECURITY_DIR" "$RUNTIME_TENANCY_DIR"
  run_root chmod -R u+rwX,g+rX,o-rwx "$RUNTIME_SECURITY_DIR" "$RUNTIME_TENANCY_DIR"

  if ! run_root runuser -u "$RUNTIME_USER" -- test -r "$RUNTIME_SECURITY_DIR"; then
    echo "[install] runtime user cannot read security state: $RUNTIME_SECURITY_DIR" >&2
    exit 1
  fi
  if ! run_root runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_SECURITY_DIR"; then
    echo "[install] runtime user cannot write security state: $RUNTIME_SECURITY_DIR" >&2
    exit 1
  fi
  if ! run_root runuser -u "$RUNTIME_USER" -- test -w "$RUNTIME_TENANCY_DIR"; then
    echo "[install] runtime user cannot write tenancy state: $RUNTIME_TENANCY_DIR" >&2
    exit 1
  fi
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

# Historical deployments stored encrypted key-provider and secret-vault state
# beneath the application checkout. Canonical systemd services use
# /var/lib/businesaios/runtime as their writable data root. Copy legacy security
# state only into an empty runtime target and verify byte-for-byte equivalence.
# On later deploys, canonical key/vault migrations intentionally make runtime
# differ from the preserved rollback source; accept that divergence only when
# every changed legacy file has a byte-identical approved migration backup and
# the live runtime file has the expected migrated shape. Unknown divergence
# remains fail-closed and the installer never overwrites non-empty runtime state.
migrate_legacy_security_state

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
