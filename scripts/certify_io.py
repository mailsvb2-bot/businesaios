from __future__ import annotations

from pathlib import Path
from typing import Iterable


def iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if "__pycache__" in parts:
            continue
        if ".venv" in parts or "venv" in parts:
            continue
        if "artifacts" in parts:
            continue
        yield p


def read_text(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except Exception:
        return ""


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
