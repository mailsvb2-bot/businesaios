from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _all_paths() -> list[str]:
    return [str(p.relative_to(PROJECT_ROOT)) for p in PROJECT_ROOT.rglob("*")]

def test_no_pycache() -> None:
    files = _all_paths()
    assert not any("__pycache__" in p for p in files)

def test_no_pyc() -> None:
    files = _all_paths()
    assert not any(p.endswith(".pyc") for p in files)

def test_no_demo_db() -> None:
    files = _all_paths()
    assert not any(p.startswith("runtime/data/demo/") and p.endswith(".db") for p in files)


def test_no_test_db() -> None:
    files = _all_paths()
    assert not any(p.startswith("runtime/data/test/") and p.endswith(".db") for p in files)
