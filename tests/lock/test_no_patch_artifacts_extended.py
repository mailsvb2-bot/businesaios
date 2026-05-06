from __future__ import annotations

import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

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


def test_no_patch_or_backup_artifacts_present() -> None:
    """Hard lock: repo must not contain merge/patch leftovers (.rej/.orig/.bak)."""
    forbidden_suffixes = (".rej", ".orig", ".bak")

    hits: list[str] = []
    for p in _iter_repo_files(REPO_ROOT):
        if p.suffix in forbidden_suffixes:
            hits.append(p.relative_to(REPO_ROOT).as_posix())

    assert not hits, "Forbidden patch/backup artifacts found:\n" + "\n".join(sorted(hits)[:200])
