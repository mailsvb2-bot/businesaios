#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

PYTHON_BIN="${PYTHON_BIN:-python}"
OUTER_BOOT_SMOKE_ROOT="${BAIOS_BOOT_SMOKE_ROOT:-/tmp/businesaios-boot-smoke}"
VERIFY_BOOT_SMOKE_ROOT="${OUTER_BOOT_SMOKE_ROOT%/}-verify-${BASHPID}"
export BAIOS_BOOT_SMOKE_ROOT="$VERIFY_BOOT_SMOKE_ROOT"

cleanup_verify_boot_smoke() {
  "$PYTHON_BIN" - "$VERIFY_BOOT_SMOKE_ROOT" <<'PY'
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1])
if root.name and "verify-" in root.name:
    shutil.rmtree(root, ignore_errors=True)
PY
}
trap cleanup_verify_boot_smoke EXIT

echo "[verify] python: $($PYTHON_BIN --version 2>/dev/null || true)"
echo "[verify] isolated boot root: $BAIOS_BOOT_SMOKE_ROOT"
echo "[verify] running bounded fast release gate"
"$PYTHON_BIN" -m scripts.ci.cli --gate fast --no-report --no-junit --no-coverage

echo "[verify] scan for artifacts"
bad=0
if find . -name "__pycache__" -type d | grep -q .; then
  echo "ERROR: __pycache__ directories found" >&2
  bad=1
fi
if find . -name "*.pyc" -type f | grep -q .; then
  echo "ERROR: *.pyc files found" >&2
  bad=1
fi
if find . -name "*.rej" -type f | grep -q .; then
  echo "ERROR: *.rej files found" >&2
  bad=1
fi
if find . -name "*.orig" -type f | grep -q .; then
  echo "ERROR: *.orig files found" >&2
  bad=1
fi
if find . \( -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.db" -o -name "*.zip" -o -name "*.tar" -o -name "*.tgz" -o -name "*.gz" -o -name "*.7z" -o -name "*.rar" \) -type f | grep -q .; then
  echo "ERROR: forbidden archive/db artifacts found" >&2
  bad=1
fi

if [[ $bad -ne 0 ]]; then
  exit 10
fi

echo "[verify] OK"
