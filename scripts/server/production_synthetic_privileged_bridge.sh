#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

APP_DIR="/opt/businesaios"
ADAPTER="$APP_DIR/scripts/server/production_synthetic_evidence.sh"
PYTHON_BIN="$APP_DIR/.venv/bin/python"
LOCK_FILE="/run/lock/businesaios-production-synthetic-evidence.lock"

fail() {
  echo "$*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "trusted production evidence bridge must run as root"
[[ "$#" -eq 1 ]] || fail "trusted production evidence bridge requires exactly one SHA"
EXPECTED_SHA="$1"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "trusted production evidence SHA must be lowercase full SHA"
[[ -x "$ADAPTER" ]] || fail "canonical production evidence adapter is missing: $ADAPTER"
[[ -x "$PYTHON_BIN" ]] || fail "canonical production Python is missing: $PYTHON_BIN"

OBSERVED_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
[[ "$OBSERVED_SHA" == "$EXPECTED_SHA" ]] || fail "deployed SHA mismatch: $OBSERVED_SHA != $EXPECTED_SHA"

exec 9>"$LOCK_FILE"
flock -n 9 || fail "another trusted production evidence run is active"
TEMP_EVIDENCE="$(mktemp "${TMPDIR:-/tmp}/businesaios-trusted-production.XXXXXX.json")"
cleanup() { rm -f "$TEMP_EVIDENCE"; }
trap cleanup EXIT

cd "$APP_DIR"
set +e
env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  HOME=/root \
  EXPECTED_SHA="$EXPECTED_SHA" \
  BUSINESAIOS_DEPLOY_ROOT="$APP_DIR" \
  PRODUCTION_ENV_FILE=/etc/businesaios/api.env \
  PRODUCTION_SYNTHETIC_EVIDENCE_PATH="$TEMP_EVIDENCE" \
  bash "$ADAPTER" >&2
VERIFY_RC=$?
set -e
(( VERIFY_RC == 0 )) || exit "$VERIFY_RC"
[[ -s "$TEMP_EVIDENCE" ]] || fail "canonical production adapter produced no evidence"

"$PYTHON_BIN" - "$EXPECTED_SHA" "$TEMP_EVIDENCE" <<'PY'
import json
import sys
from pathlib import Path

expected_sha, evidence_file = sys.argv[1:]
payload = json.loads(Path(evidence_file).read_text(encoding="utf-8"))
allowed = {
    "schema", "status", "exact_sha", "observed_sha", "environment",
    "tenant_id", "synthetic_run_id", "checks", "source", "violations",
    "claims_production_ready",
}
unexpected = set(payload) - allowed
if unexpected:
    raise SystemExit(f"unexpected production evidence fields: {sorted(unexpected)!r}")
if payload.get("schema") != "businessaios_production_synthetic_evidence.v1":
    raise SystemExit("invalid production evidence schema")
if payload.get("status") != "PASS":
    raise SystemExit("production evidence is not PASS")
if payload.get("exact_sha") != expected_sha:
    raise SystemExit("production evidence exact SHA mismatch")
if payload.get("claims_production_ready") is not False:
    raise SystemExit("production evidence must remain factual-only")
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
PY
