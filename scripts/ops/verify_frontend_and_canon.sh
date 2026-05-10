#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="${1:-/opt/businesaios}"
cd "$ROOT_DIR"

python3 -m pytest -q tests/decision_runtime/test_canonical_flow_contract.py

test -f frontend/package.json || { echo "missing frontend/package.json"; exit 1; }
test -f frontend/src/App.jsx || { echo "missing frontend/src/App.jsx"; exit 1; }

echo "verify: OK"
