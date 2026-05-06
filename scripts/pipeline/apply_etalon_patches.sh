#!/usr/bin/env bash
set -euo pipefail

# Apply a directory of unified-diff patch files to the repo.
# Canonical: uses `patch` (no git dependency) and fails fast on conflicts.

PATCH_DIR=${1:-""}
if [[ -z "$PATCH_DIR" ]]; then
  echo "Usage: $0 <patch_dir>" >&2
  exit 2
fi

if [[ ! -d "$PATCH_DIR" ]]; then
  echo "Patch dir not found: $PATCH_DIR" >&2
  exit 2
fi

shopt -s nullglob
PATCHES=("$PATCH_DIR"/*.diff "$PATCH_DIR"/*.patch)
if (( ${#PATCHES[@]} == 0 )); then
  echo "No patches found in $PATCH_DIR" >&2
  exit 2
fi

for p in "${PATCHES[@]}"; do
  echo "Applying $p"
  patch -p1 --forward < "$p"
done

echo "OK"
