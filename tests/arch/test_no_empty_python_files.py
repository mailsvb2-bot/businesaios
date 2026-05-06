from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_empty_python_files() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        if path.is_file() and not path.read_text(encoding="utf-8").strip():
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"empty python files found: {offenders}"
