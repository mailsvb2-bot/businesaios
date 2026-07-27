from __future__ import annotations

from pathlib import Path

from scripts.ci.repository_sources import (
    iter_repository_python_files,
    read_python_source,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def iter_python_files() -> tuple[Path, ...]:
    return iter_repository_python_files(project_root())


def read_text(path: Path) -> str:
    return read_python_source(path)
