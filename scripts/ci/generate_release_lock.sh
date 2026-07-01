#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INPUT="${INPUT:-$ROOT/requirements.txt}"
OUTPUT="${OUTPUT:-$ROOT/requirements.release.lock.txt}"
PYTHON_BIN="${PYTHON_BIN:-python}"

step() {
  printf '\n== %s ==\n' "$1"
}

if [[ ! -f "$INPUT" ]]; then
  echo "missing requirements input: $INPUT" >&2
  exit 1
fi

TMP="$(mktemp)"
cleanup() {
  rm -f "$TMP"
}
trap cleanup EXIT

step "generate transitive dependency lock"
if command -v uv >/dev/null 2>&1; then
  uv pip compile "$INPUT" --generate-hashes -o "$TMP"
elif command -v pip-compile >/dev/null 2>&1; then
  pip-compile "$INPUT" --generate-hashes --output-file "$TMP"
else
  echo "missing lock generator: install uv or pip-tools" >&2
  echo "examples:" >&2
  echo "  python -m pip install uv" >&2
  echo "  python -m pip install pip-tools" >&2
  exit 1
fi

{
  echo "# BAIOS_TRANSITIVE_LOCK: true"
  echo "# Generated from requirements.txt. Do not edit by hand."
  echo "# Regenerate with: bash scripts/ci/generate_release_lock.sh"
  cat "$TMP"
} > "$OUTPUT"

step "verify dependency lock contract"
BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1 "$PYTHON_BIN" "$ROOT/scripts/ci/check_requirements_lock.py"

echo "release dependency lock written: $OUTPUT"
