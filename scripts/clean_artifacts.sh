#!/usr/bin/env bash
set -euo pipefail

# Release hygiene: remove build/test artifacts.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -type f -delete
find . -name ".pytest_cache" -type d -prune -exec rm -rf {} +

echo "OK: artifacts cleaned"

find . -name ".mypy_cache" -type d -prune -exec rm -rf {} +
find . -name ".ruff_cache" -type d -prune -exec rm -rf {} +
find . -name ".runtime" -type d -prune -exec rm -rf {} +
find . -path "./artifacts/ci" -type d -prune -exec rm -rf {} +
find . \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.lock" \) -type f -delete

find . -name ".release_tmp" -type d -prune -exec rm -rf {} +
