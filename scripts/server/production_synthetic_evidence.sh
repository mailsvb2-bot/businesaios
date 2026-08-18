#!/usr/bin/env bash
set -Eeuo pipefail

BUSINESAIOS_DEPLOY_ROOT="${BUSINESAIOS_DEPLOY_ROOT:-/opt/businesaios}"
PYTHON_BIN="$BUSINESAIOS_DEPLOY_ROOT/.venv/bin/python"
HOST_VERIFY="$BUSINESAIOS_DEPLOY_ROOT/scripts/server/verify_runtime_host_contract.sh"
EXPECTED_SHA="${EXPECTED_SHA:-}"

[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "EXPECTED_SHA must be a full 40-character git SHA" >&2
  exit 1
}
EXPECTED_SHA="${EXPECTED_SHA,,}"
[[ -x "$PYTHON_BIN" ]] || { echo "canonical production Python is missing: $PYTHON_BIN" >&2; exit 1; }
[[ -x "$HOST_VERIFY" ]] || { echo "canonical production host verifier is missing: $HOST_VERIFY" >&2; exit 1; }

EVIDENCE_DIR="${PRODUCTION_SYNTHETIC_EVIDENCE_DIR:-/var/lib/businesaios/runtime/reports/post-deploy}"
EVIDENCE_PATH="${PRODUCTION_SYNTHETIC_EVIDENCE_PATH:-$EVIDENCE_DIR/production-synthetic-$EXPECTED_SHA.json}"
TEMP_VERDICT="$(mktemp "${TMPDIR:-/tmp}/businesaios-production-probe.XXXXXX.json")"
cleanup() { rm -f "$TEMP_VERDICT"; }
trap cleanup EXIT

set +e
PRODUCTION_VERDICT_PATH="$TEMP_VERDICT" EXPECTED_SHA="$EXPECTED_SHA" "$HOST_VERIFY"
VERIFY_RC=$?
set -e

LEGACY_PROBE_PATH="$TEMP_VERDICT" EVIDENCE_PATH="$EVIDENCE_PATH" VERIFY_RC="$VERIFY_RC" EXPECTED_SHA="$EXPECTED_SHA" "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

legacy_path = Path(os.environ["LEGACY_PROBE_PATH"])
evidence_path = Path(os.environ["EVIDENCE_PATH"])
expected_sha = os.environ["EXPECTED_SHA"]
verify_rc = int(os.environ["VERIFY_RC"])

try:
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    legacy = {}

legacy_verdict = str(legacy.get("verdict") or "").lower()
status = "PASS" if verify_rc == 0 and legacy_verdict == "pass" else "FAIL"
payload = {
    "schema": "businessaios_production_synthetic_evidence.v1",
    "status": status,
    "exact_sha": expected_sha,
    "observed_sha": legacy.get("observed_sha"),
    "environment": legacy.get("environment"),
    "tenant_id": legacy.get("tenant_id"),
    "synthetic_run_id": legacy.get("synthetic_run_id"),
    "checks": legacy.get("checks") if isinstance(legacy.get("checks"), dict) else {},
    "source": "scripts/server/verify_runtime_host_contract.sh",
    "violations": [] if status == "PASS" else [str(legacy.get("error") or f"host_probe_exit_{verify_rc}")],
    "claims_production_ready": False,
}
evidence_path.parent.mkdir(parents=True, exist_ok=True)
tmp = evidence_path.with_name(f".{evidence_path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(evidence_path)
print(f"PRODUCTION_SYNTHETIC_EVIDENCE status={status} sha={expected_sha} path={evidence_path}")
PY

exit "$VERIFY_RC"
