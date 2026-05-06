from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.lock
def test_no_zip_or_sqlite_artifacts_in_repo() -> None:
    """Super-lock: forbid accidental archives/DB files in repo.

    Bounded implementation: use `find` with explicit prunes instead of a
    Python-wide tree walk. This preserves the release hygiene invariant while
    preventing historical/generated directories from making the fast gate hang.
    """

    repo = Path(__file__).resolve().parents[2]
    cmd = [
        "find", ".",
        "(", "-path", "./.git", "-o", "-path", "./.artifacts", "-o", "-path", "./artifacts",
        "-o", "-path", "./.venv", "-o", "-path", "./venv",
        "-o", "-path", "./__pycache__", "-o", "-path", "*/__pycache__",
        "-o", "-path", "./.pytest_cache", "-o", "-path", "./.mypy_cache", "-o", "-path", "./.ruff_cache",
        ")", "-prune", "-o",
        "-type", "f",
        "(", "-name", "*.zip", "-o", "-name", "*.sqlite", "-o", "-name", "*.sqlite3", "-o", "-name", "*.db",
        "-o", "-name", "*.tar", "-o", "-name", "*.gz", "-o", "-name", "*.tgz", "-o", "-name", "*.7z", "-o", "-name", "*.rar", ")",
        "-print",
    ]
    completed = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, timeout=15, check=False)
    assert completed.returncode == 0, completed.stderr
    bad = [line.removeprefix("./") for line in completed.stdout.splitlines() if not line.startswith("./tests/fixtures/")]
    assert not bad, f"Forbidden archive/db artifacts in repo: {bad[:20]}"
