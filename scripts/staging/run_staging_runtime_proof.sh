#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PYTHON_BIN" >&2
  echo "Create/install the project venv first, then run: .venv/bin/pip install -r requirements.txt" >&2
  exit 2
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required for real staging proof" >&2
  exit 2
fi

"$PYTHON_BIN" - <<'PY'
import importlib.util
import sys
if importlib.util.find_spec("psycopg") is None:
    print("psycopg is required for real staging proof; run: .venv/bin/pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)
PY

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for real staging container proof, but docker was not found in PATH." >&2
  echo "Install Docker on the staging server before running this proof." >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not reachable by this user." >&2
  echo "Start Docker and/or grant this operator access before running staging proof." >&2
  exit 2
fi

IMAGE="${BAIOS_STAGING_IMAGE:-businesaios:staging-proof}"
PYTHON_BASE_IMAGE="${BAIOS_PYTHON_BASE_IMAGE:-businesaios/python-runtime-base:3.12-slim}"
CONTAINER="${BAIOS_STAGING_CONTAINER:-businesaios-staging-proof}"
HOST="${BAIOS_STAGING_HOST:-127.0.0.1}"
HOST_PORT="${BAIOS_STAGING_PORT:-18000}"
CONTAINER_PORT="${BAIOS_CONTAINER_PORT:-8000}"
TIMEOUT_SECONDS="${BAIOS_STAGING_TIMEOUT_SECONDS:-120}"
ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/ci}"
CONTROL_PLANE_API_KEY_PEPPER="${API_CONTROL_PLANE_API_KEY_PEPPER:-}"
if [[ -z "$CONTROL_PLANE_API_KEY_PEPPER" ]]; then
  CONTROL_PLANE_API_KEY_PEPPER="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')"
fi
if [[ -z "$CONTROL_PLANE_API_KEY_PEPPER" ]]; then
  echo "Could not create a non-empty control-plane API-key pepper for staging proof." >&2
  exit 2
fi
CONTROL_PLANE_API_KEY_STORE_PATH="${BAIOS_STAGING_API_KEY_STORE_PATH:-/app/data/api/api_keys.json}"
if [[ "$CONTROL_PLANE_API_KEY_STORE_PATH" != /* ]]; then
  echo "BAIOS_STAGING_API_KEY_STORE_PATH must be an absolute container path." >&2
  exit 2
fi
GIT_COMMIT_SHA="${GIT_COMMIT_SHA:-$(git rev-parse --verify HEAD 2>/dev/null || true)}"
if [[ -z "$GIT_COMMIT_SHA" ]]; then
  echo "GIT_COMMIT_SHA could not be resolved; staging proof must be tied to an exact commit." >&2
  exit 2
fi
BAIOS_STAGING_PROOF_ID="${BAIOS_STAGING_PROOF_ID:-staging-${GIT_COMMIT_SHA}-$(date -u +%Y%m%dT%H%M%SZ)}"
export GIT_COMMIT_SHA BAIOS_STAGING_PROOF_ID

mkdir -p "$ARTIFACT_DIR"

if ! docker image inspect "$PYTHON_BASE_IMAGE" >/dev/null 2>&1; then
  echo "Required local base image is missing: $PYTHON_BASE_IMAGE" >&2
  echo "Staging proof does not pull base images implicitly." >&2
  echo "Prepare it explicitly, for example:" >&2
  echo "  docker pull python:3.12-slim" >&2
  echo "  docker tag python:3.12-slim $PYTHON_BASE_IMAGE" >&2
  echo "or load/tag a vetted private mirror image before running this proof." >&2
  exit 2
fi

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

run_gate() {
  local gate="$1"
  "$PYTHON_BIN" -m scripts.ci.cli --gate "$gate"
}

export APP_PROFILE=api
export ENV=production
export APP_ENV=production
export POSTGRES_RUNTIME_ENABLED=1
export POSTGRES_EVENT_STORE_ENABLED=1
export POSTGRES_APPLY_MIGRATIONS=1
export RUN_MIGRATIONS_BEFORE_START=1
export BAIOS_REQUIRE_QUALITY_TOOLS=release

# Real staging order matters: migrations create durable schema first;
# contract and live proofs must validate the migrated database, not an empty one.
run_gate postgres-migrations
run_gate postgres-contract
run_gate postgres-live

"$PYTHON_BIN" scripts/staging/write_staging_release_manifest.py >/dev/null
test -s release/manifest.json

docker build --pull=false --build-arg PYTHON_BASE_IMAGE="$PYTHON_BASE_IMAGE" -t "$IMAGE" .
cleanup

docker run -d \
  --name "$CONTAINER" \
  --label businesaios.proof=staging-runtime \
  -p "${HOST}:${HOST_PORT}:${CONTAINER_PORT}" \
  -e APP_PROFILE=api \
  -e API_HOST=0.0.0.0 \
  -e API_PORT="$CONTAINER_PORT" \
  -e ENV=production \
  -e APP_ENV=production \
  -e API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS=0 \
  -e API_CONTROL_PLANE_API_KEY_PEPPER="$CONTROL_PLANE_API_KEY_PEPPER" \
  -e BUSINESAIOS_API_KEY_STORE_BACKEND=file \
  -e BUSINESAIOS_API_KEY_STORE_PATH="$CONTROL_PLANE_API_KEY_STORE_PATH" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e POSTGRES_RUNTIME_ENABLED=1 \
  -e POSTGRES_EVENT_STORE_ENABLED=1 \
  -e RUN_MIGRATIONS_BEFORE_START=1 \
  -e BAIOS_REQUIRE_QUALITY_TOOLS=release \
  "$IMAGE" >/dev/null

probe_url() {
  local path="$1"
  HEALTH_URL="http://${HOST}:${HOST_PORT}${path}" HEALTHCHECK_REQUIRE_READY=1 "$PYTHON_BIN" scripts/healthcheck.py >/dev/null
}

wait_for_readyz() {
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  until probe_url /readyz; do
    if (( SECONDS >= deadline )); then
      echo "container readiness timeout for /readyz" >&2
      docker logs "$CONTAINER" >&2 || true
      return 1
    fi
    sleep 2
  done
}

wait_for_readyz
probe_url /storagez
probe_url /executionz

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

artifact_dir = Path("artifacts/ci")
base_image = os.environ.get("BAIOS_PYTHON_BASE_IMAGE", "businesaios/python-runtime-base:3.12-slim")
payload = {
    "artifact": "container_runtime_evidence",
    "status": "ready",
    "evidence_kind": "real_container_runtime_probe",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "proof_id": os.environ["BAIOS_STAGING_PROOF_ID"],
    "commit_sha": os.environ["GIT_COMMIT_SHA"],
    "image": os.environ.get("BAIOS_STAGING_IMAGE", "businesaios:staging-proof"),
    "base_image": base_image,
    "base_image_pull_policy": "never_during_staging_proof",
    "container_name": os.environ.get("BAIOS_STAGING_CONTAINER", "businesaios-staging-proof"),
    "image_built": True,
    "container_started": True,
    "readyz_ok": True,
    "storagez_ok": True,
    "executionz_ok": True,
    "uses_readiness_healthcheck": True,
    "probe_urls": ["/readyz", "/storagez", "/executionz"],
    "claims_production_ready": False,
}
(artifact_dir / "container_runtime_evidence.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY

export CONTAINER_RUNTIME_PROOF_REQUIRED=1
export CONTAINER_RUNTIME_EVIDENCE_REQUIRED=1
export REAL_RUNTIME_BOOT_EVIDENCE_REQUIRED=1

run_gate container-runtime

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

artifact_dir = Path("artifacts/ci")
container_runtime = json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8"))
postgres_contract = json.loads((artifact_dir / "postgres_contract.json").read_text(encoding="utf-8"))
postgres_migrations = json.loads((artifact_dir / "postgres_migrations.json").read_text(encoding="utf-8"))
postgres_live = json.loads((artifact_dir / "postgres_live.json").read_text(encoding="utf-8"))
payload = {
    "artifact": "real_runtime_boot_evidence",
    "status": "ready",
    "evidence_kind": "real_staging_runtime_boot_probe",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "proof_id": os.environ["BAIOS_STAGING_PROOF_ID"],
    "commit_sha": os.environ["GIT_COMMIT_SHA"],
    "postgres_contract_ready": postgres_contract.get("status") == "ready",
    "postgres_migrations_ready": postgres_migrations.get("status") == "ready",
    "postgres_live_ready": postgres_live.get("status") == "ready",
    "container_runtime_ready": container_runtime.get("status") == "ready",
    "readyz_ok": container_runtime.get("readyz_ok") is True,
    "storagez_ok": container_runtime.get("storagez_ok") is True,
    "executionz_ok": container_runtime.get("executionz_ok") is True,
    "claims_production_ready": False,
}
required = (
    "postgres_contract_ready",
    "postgres_migrations_ready",
    "postgres_live_ready",
    "container_runtime_ready",
    "readyz_ok",
    "storagez_ok",
    "executionz_ok",
)
violations = [f"{name}_required" for name in required if payload.get(name) is not True]
if violations:
    payload["status"] = "blocked"
    payload["violations"] = violations
(artifact_dir / "real_runtime_boot_evidence.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if payload["status"] == "ready" else 1)
PY

run_gate production-boot

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

artifact_dir = Path("artifacts/ci")
summary = {
    "artifact": "staging_runtime_proof",
    "status": "ready",
    "evidence_kind": "real_staging_runtime_proof",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "proof_id": os.environ["BAIOS_STAGING_PROOF_ID"],
    "commit_sha": os.environ["GIT_COMMIT_SHA"],
    "base_image": os.environ.get("BAIOS_PYTHON_BASE_IMAGE", "businesaios/python-runtime-base:3.12-slim"),
    "base_image_pull_policy": "never_during_staging_proof",
    "release_manifest": json.loads(Path("release/manifest.json").read_text(encoding="utf-8")),
    "container_runtime_evidence": json.loads((artifact_dir / "container_runtime_evidence.json").read_text(encoding="utf-8")),
    "real_runtime_boot_evidence": json.loads((artifact_dir / "real_runtime_boot_evidence.json").read_text(encoding="utf-8")),
    "postgres_contract": json.loads((artifact_dir / "postgres_contract.json").read_text(encoding="utf-8")),
    "postgres_migrations": json.loads((artifact_dir / "postgres_migrations.json").read_text(encoding="utf-8")),
    "postgres_live": json.loads((artifact_dir / "postgres_live.json").read_text(encoding="utf-8")),
    "container_runtime": json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8")),
    "production_boot": json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8")),
    "claims_production_ready": False,
}
required_ready = (
    "postgres_contract",
    "postgres_migrations",
    "postgres_live",
    "container_runtime",
    "container_runtime_evidence",
    "real_runtime_boot_evidence",
)
blocked = [name for name in required_ready if summary[name].get("status") != "ready"]
if summary["production_boot"].get("status") != "contract_satisfied":
    blocked.append("production_boot")
if blocked:
    summary["status"] = "blocked"
    summary["violations"] = [f"{name}_not_ready" for name in blocked]
(artifact_dir / "staging_runtime_proof.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if summary["status"] == "ready" else 1)
PY
