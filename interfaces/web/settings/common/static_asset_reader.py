from __future__ import annotations

from pathlib import Path


def read_text_asset(*, root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")
