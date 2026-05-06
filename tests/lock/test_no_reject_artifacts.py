from __future__ import annotations

import os
import pathlib

import pytest

_SKIP_DIRS = {
    ".git", ".artifacts", "artifacts", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def _iter_repo_files(root: pathlib.Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIRS]
        base = pathlib.Path(dirpath)
        for filename in filenames:
            yield base / filename


@pytest.mark.lock
def test_no_reject_artifacts_present():
    root = pathlib.Path(__file__).resolve().parents[2]
    rejects = [p.relative_to(root).as_posix() for p in _iter_repo_files(root) if p.suffix == ".rej"]
    assert rejects == [], f"reject artifacts present: {rejects[:200]}"
