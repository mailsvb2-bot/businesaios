from __future__ import annotations

from pathlib import Path

from scripts.ci.repository_sources import (
    iter_repository_python_files,
    read_python_source,
)

ROOT = Path(__file__).resolve().parents[2]


def python_files() -> list[Path]:
    return list(iter_repository_python_files(ROOT))


def file_level_compile_failures() -> list[str]:
    failures: list[str] = []
    for path in python_files():
        try:
            source = read_python_source(path)
            compile(source, str(path), "exec")
        except Exception:
            failures.append(str(path.relative_to(ROOT)))
    return failures
