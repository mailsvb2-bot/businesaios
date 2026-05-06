#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/release_clean.zip}"

cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1

# Canonical packer already performs cleanup and stable zip.
python scripts/release_clean_pack.py "$OUT"
echo "$OUT"
