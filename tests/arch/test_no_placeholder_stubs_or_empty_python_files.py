from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_empty_python_files_exist() -> None:
    empty = []
    for path in ROOT.rglob("*.py"):
        if path.is_file() and path.stat().st_size == 0:
            empty.append(path.relative_to(ROOT).as_posix())
    assert empty == [], empty
