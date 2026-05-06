from __future__ import annotations

from pathlib import Path

IGNORE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".tox", ".eggs",
    "site-packages", "node_modules",
}

NEEDLES = (
    "from core.economic ",
    "from core.economic\n",
    "from core.economic.",
    "import core.economic",
    "core.economic.",
)

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def test_no_core_economic_namespace_left():
    root = _repo_root()
    offenders = []
    for p in root.rglob("*.py"):
        if p.name == "test_no_economic_namespace_split.py":
            continue
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        if any(n in src for n in NEEDLES):
            offenders.append(p.relative_to(root))
    assert not offenders, "Found legacy core.economic imports/strings:\n" + "\n".join(map(str, offenders))
