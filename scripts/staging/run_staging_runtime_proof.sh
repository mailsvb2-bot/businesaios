#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT_DIR"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required for real staging proof" >&2
  exit 2
fi

IMAGE="${BAIOS_STAGING_IMAGE:-businesaios:staging-proof}"
CONTAINER="${BAIOS_STAGING_CONTAINER:-businesaios-staging-proof}"
HOST="${BAIOS_STAGING_HOST:-127.0.0.1}"
HOST_PORT="${BAIOS_STAGING_PORT:-18000}"
CONTAINER_PORT="${BAIOS_CONTAINER_PORT:-8000}"
TIMEOUT_SECONDS="${BAIOS_STAGING_TIMEOUT_SECONDS:-120}"
ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/ci}"

mkdir -p "$ARTIFACT_DIR"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

run_gate() {
  local gate="$1"
  python -m scripts.ci.cli --gate "$gate"
}

export APP_PROFILE=api
export ENV=production
export APP_ENV=production
export POSTGRES_RUNTIME_ENABLED=1
export POSTGRES_EVENT_STORE_ENABLED=1
export POSTGRES_APPLY_MIGRATIONS=1
export RUN_MIGRATIONS_BEFORE_START=1
export BAIOS_REQUIRE_QUALITY_TOOLS=release

run_gate postgres-contract
run_gate postgres-migrations
run_gate postgres-live

docker build -t "$IMAGE" .
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
  -e DATABASE_URL="$DATABASE_URL" \
  -e POSTGRES_RUNTIME_ENABLED=1 \
  -e POSTGRES_EVENT_STORE_ENABLED=1 \
  -e RUN_MIGRATIONS_BEFORE_START=1 \
  -e BAIOS_REQUIRE_QUALITY_TOOLS=release \
  "$IMAGE" >/dev/null

probe_url() {
  local path="$1"
  HEALTH_URL="http://${HOST}:${HOST_PORT}${path}" HEALTHCHECK_REQUIRE_READY=1 python scripts/healthcheck.py >/dev/null
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

export CONTAINER_RUNTIME_PROOF_REQUIRED=1
export CONTAINER_IMAGE_BUILT=1
export CONTAINER_STARTED=1
export CONTAINER_READYZ_OK=1
export CONTAINER_STORAGEZ_OK=1
export CONTAINER_EXECUTIONZ_OK=1
export CONTAINER_READINESS_HEALTHCHECK_OK=1

run_gate container-runtime
run_gate production-boot

python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

artifact_dir = Path("artifacts/ci")
summary = {
    "artifact": "staging_runtime_proof",
    "status": "ready",
    "postgres_contract": json.loads((artifact_dir / "postgres_contract.json").read_text(encoding="utf-8")),
    "postgres_migrations": json.loads((artifact_dir / "postgres_migrations.json").read_text(encoding="utf-8")),
    "postgres_live": json.loads((artifact_dir / "postgres_live.json").read_text(encoding="utf-8")),
    "container_runtime": json.loads((artifact_dir / "container_runtime.json").read_text(encoding="utf-8")),
    "production_boot": json.loads((artifact_dir / "production_boot.json").read_text(encoding="utf-8")),
    "claims_production_ready": False,
}
required_ready = ("postgres_contract", "postgres_migrations", "postgres_live", "container_runtime")
blocked = [name for name in required_ready if summary[name].get("status") != "ready"]
if blocked:
    summary["status"] = "blocked"
    summary["violations"] = [f"{name}_not_ready" for name in blocked]
(artifact_dir / "staging_runtime_proof.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if summary["status"] == "ready" else 1)
PY
