from __future__ import annotations

from pathlib import Path

from scripts.ci.paths import repo_root


def makefile_path() -> Path:
    return repo_root() / "Makefile"


def has_make_target(target_name: str) -> bool:
    path = makefile_path()
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8")
    if text.startswith(f"{target_name}:"):
        return True
    return f"\n{target_name}:" in text
