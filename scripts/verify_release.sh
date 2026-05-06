#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

echo "[verify] python: $(python --version 2>/dev/null || true)"
echo "[verify] running bounded fast release gate"
python -m scripts.ci.cli --gate fast --no-report --no-junit --no-coverage

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
