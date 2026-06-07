from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator

from .constants import CANON_DOMAIN_MARKER, STRATEGIC_DOMAIN_NAMES

_TRANSIENT_NAMES: frozenset[str] = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def is_transient_path(path: Path) -> bool:
    return any(part in _TRANSIENT_NAMES for part in path.parts)


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def line_count(path: Path) -> int:
    return len(read_text_safe(path).splitlines())


def iter_canon_domains(root: Path) -> Iterator[Path]:
    core = root / "core"
    if not core.exists():
        return

    for domain_name in STRATEGIC_DOMAIN_NAMES:
        domain = core / domain_name
        marker = domain / CANON_DOMAIN_MARKER
        if domain.is_dir() and marker.exists():
            yield domain
