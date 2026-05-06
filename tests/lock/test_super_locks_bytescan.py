from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.lock
def test_no_conflict_markers_bytescan_outside_tests() -> None:
    """Super-lock: forbid *actual* merge-conflict blocks outside tests.

    Bounded implementation: scan relevant small text files only and prune
    generated/cache/artifact directories. The invariant is still the same:
    no real conflict triad may exist in shipped source/config/docs surfaces.
    """

    repo = Path(__file__).resolve().parents[2]
    cmd = [
        "find", ".",
        "(", "-path", "./.git", "-o", "-path", "./.artifacts", "-o", "-path", "./artifacts",
        "-o", "-path", "./tests", "-o", "-path", "./.venv", "-o", "-path", "./venv",
        "-o", "-path", "./__pycache__", "-o", "-path", "*/__pycache__",
        "-o", "-path", "./.pytest_cache", "-o", "-path", "./.mypy_cache", "-o", "-path", "./.ruff_cache",
        ")", "-prune", "-o",
        "-type", "f", "-size", "-2M",
        "(", "-name", "*.py", "-o", "-name", "*.md", "-o", "-name", "*.yml", "-o", "-name", "*.yaml",
        "-o", "-name", "*.toml", "-o", "-name", "*.ini", "-o", "-name", "*.json", "-o", "-name", "*.txt",
        "-o", "-name", "*.sh", "-o", "-name", "Dockerfile", "-o", "-name", "Makefile", ")",
        "-print",
    ]
    completed = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, timeout=15, check=False)
    assert completed.returncode == 0, completed.stderr
    bad: list[str] = []
    for raw in completed.stdout.splitlines():
        p = repo / raw.removeprefix("./")
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if b"<<<<<<<" in data and b"=======" in data and b">>>>>>>" in data:
            bad.append(raw.removeprefix("./"))
    assert not bad, f"Merge conflict blocks found outside tests: {bad[:20]}"
