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
CONSTRAINTS="$(mktemp)"
cleanup() {
  rm -f "$TMP" "$CONSTRAINTS"
}
trap cleanup EXIT

# Preserve the last proven transitive graph unless an operator explicitly asks
# for a full dependency refresh. Top-level requirements are excluded from the
# baseline so intentional direct-version changes remain possible.
if [[ -f "$OUTPUT" && "${BAIOS_LOCK_UPGRADE_ALL:-0}" != "1" ]]; then
  "$PYTHON_BIN" - "$INPUT" "$OUTPUT" "$CONSTRAINTS" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

input_path, output_path, constraints_path = map(Path, sys.argv[1:])
name_re = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(?:\[[^]]+\])?\s*==")
locked_re = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")

def normalize(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()

top_level: set[str] = set()
for raw in input_path.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].strip()
    match = name_re.match(line)
    if match:
        top_level.add(normalize(match.group(1)))

constraints: list[str] = []
for raw in output_path.read_text(encoding="utf-8").splitlines():
    match = locked_re.match(raw.strip())
    if not match or normalize(match.group(1)) in top_level:
        continue
    constraints.append(f"{match.group(1)}=={match.group(2)}")

constraints_path.write_text("\n".join(constraints) + ("\n" if constraints else ""), encoding="utf-8")
PY
fi

step "generate transitive dependency lock"
CONSTRAINT_ARGS=()
if [[ -s "$CONSTRAINTS" ]]; then
  CONSTRAINT_ARGS=(--constraint "$CONSTRAINTS")
fi
if command -v uv >/dev/null 2>&1; then
  uv pip compile "$INPUT" "${CONSTRAINT_ARGS[@]}" --generate-hashes -o "$TMP"
elif command -v pip-compile >/dev/null 2>&1; then
  pip-compile "$INPUT" "${CONSTRAINT_ARGS[@]}" --generate-hashes --output-file "$TMP"
else
  echo "missing lock generator: install uv or pip-tools" >&2
  echo "examples:" >&2
  echo "  python -m pip install uv" >&2
  echo "  python -m pip install pip-tools" >&2
  exit 1
fi

# Constraint files are an implementation detail. Remove their random paths from
# annotations and restore canonical single-source `# via` lines so repeated
# lock generation is byte-stable when the dependency graph has not changed.
"$PYTHON_BIN" - "$TMP" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
out: list[str] = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    if stripped.startswith("#    uv pip compile "):
        out.append("#    uv pip compile requirements.txt --generate-hashes")
        i += 1
        continue
    if stripped == "# via":
        indent = line[: line.index("#")]
        items: list[str] = []
        j = i + 1
        while j < len(lines) and lines[j].strip().startswith("#   "):
            item = lines[j].strip()[4:].strip()
            if not item.startswith("-c ") and not item.startswith("--constraint "):
                items.append(item)
            j += 1
        if len(items) == 1:
            out.append(f"{indent}# via {items[0]}")
        elif items:
            out.append(f"{indent}# via")
            out.extend(f"{indent}#   {item}" for item in items)
        i = j
        continue
    out.append(line)
    i += 1
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

{
  echo "# BAIOS_TRANSITIVE_LOCK: true"
  echo "# Generated from requirements.txt. Do not edit by hand."
  echo "# Regenerate with: bash scripts/ci/generate_release_lock.sh"
  cat "$TMP"
} > "$OUTPUT"

step "verify dependency lock contract"
BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1 "$PYTHON_BIN" "$ROOT/scripts/ci/check_requirements_lock.py"

echo "release dependency lock written: $OUTPUT"
