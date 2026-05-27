from __future__ import annotations

import json
from pathlib import Path

from canon.surface_ceiling import is_canonical_source_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _count_metrics():
    total_files = 0
    python_files = 0
    python_lines = 0

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PROJECT_ROOT)
        if not is_canonical_source_path(rel) or rel.parts[0] == "tests":
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        total_files += 1
        if path.suffix == ".py":
            python_files += 1
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
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

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    current = _count_metrics()

    assert current["total_files"] <= baseline["total_files"], current
    assert current["python_files"] <= baseline["python_files"], current
    assert current["total_python_lines"] <= baseline["total_python_lines"], current
