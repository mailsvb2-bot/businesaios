from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _count_metrics():
    total_files = 0
    python_files = 0
    python_lines = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [
            d
            for d in dirs
            if d not in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".runtime", ".artifacts", "artifacts", "tests"}
        ]
        for fn in files:
            if fn.endswith((".pyc", ".pyo")):
                continue
            total_files += 1
            if fn.endswith(".py"):
                python_files += 1
                full = os.path.join(root, fn)
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                        python_lines += sum(1 for _ in fh)
                except Exception:
                    pass

    return {
        "total_files": total_files,
        "python_files": python_files,
        "total_python_lines": python_lines,
    }

def test_canon_file_exists():
    assert (PROJECT_ROOT / "canon" / "collapse_principles.py").exists()

def test_metrics_do_not_grow():
    baseline_path = PROJECT_ROOT / "canon" / "metrics_baseline.json"
    assert baseline_path.exists()

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    current = _count_metrics()

    assert current["total_files"] <= baseline["total_files"], current
    assert current["python_files"] <= baseline["python_files"], current
    assert current["total_python_lines"] <= baseline["total_python_lines"], current
