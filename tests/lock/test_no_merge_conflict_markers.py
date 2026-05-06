from __future__ import annotations

import subprocess
from pathlib import Path

TEXT_NAMES = {"Dockerfile", "Makefile", ".gitignore"}
TEXT_SUFFIXES = {
    ".py", ".md", ".yml", ".yaml", ".toml", ".ini", ".json", ".txt", ".sh", ".env", ".cfg",
}


def test_no_merge_conflict_markers() -> None:
    """Lock: no unresolved git conflict sentinels in repo text surfaces.

    Bounded implementation: prune generated/cache/artifact directories and scan
    small text/source/config files only. Lock tests may contain marker strings,
    so the tests tree is intentionally excluded from this repo hygiene scan.
    """

    repo = Path(__file__).resolve().parents[2]
    cmd = [
        "find", ".",
        "(", "-path", "./.git", "-o", "-path", "./.artifacts", "-o", "-path", "./artifacts",
        "-o", "-path", "./tests", "-o", "-path", "./.venv", "-o", "-path", "./venv",
        "-o", "-path", "./__pycache__", "-o", "-path", "*/__pycache__",
        "-o", "-path", "./.pytest_cache", "-o", "-path", "./.mypy_cache", "-o", "-path", "./.ruff_cache",
        ")", "-prune", "-o", "-type", "f", "-size", "-2M", "-print",
    ]
    completed = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, timeout=15, check=False)
    assert completed.returncode == 0, completed.stderr

    hits: list[str] = []
    for raw in completed.stdout.splitlines():
        rel = raw.removeprefix("./")
        p = repo / rel
        if p.name not in TEXT_NAMES and p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "<<<<<<<" in text or ">>>>>>>" in text:
            hits.append(rel)

    assert not hits, "Merge conflict markers found:\n" + "\n".join(sorted(hits)[:200])
