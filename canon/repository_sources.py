"""Canonical passive inventory of repository Python sources.

This module owns filesystem boundaries only. It does not classify architecture,
select business actions, inspect decision semantics, or execute effects.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from pathlib import Path

CANON_REPOSITORY_SOURCE_INVENTORY = True

DEFAULT_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".runtime",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
        "target",
        "venv",
    }
)
DEFAULT_ROOT_EXCLUDED_DIR_NAMES = frozenset(
    {
        "artifacts",
        "build",
        "data",
        "dist",
        "htmlcov",
        "release_dist",
        "reports",
    }
)


class RepositorySourceError(RuntimeError):
    """Raised when an in-scope source cannot be inventoried or read."""


def validate_repository_root(root: Path | str) -> Path:
    if isinstance(root, str):
        root = Path(root)
    if not isinstance(root, Path):
        raise ValueError("repository root must be a path")
    try:
        resolved = root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("repository root must exist") from exc
    if not resolved.is_dir():
        raise ValueError("repository root must be a directory")
    return resolved


def _normalized_prefixes(prefixes: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in prefixes:
        if not isinstance(value, str):
            raise ValueError("excluded prefixes must be strings")
        candidate = value.strip().replace("\\", "/").lstrip("/")
        if not candidate:
            continue
        normalized.append(candidate.rstrip("/") + "/")
    return tuple(sorted(set(normalized)))


def iter_repository_python_files(
    root: Path | str,
    *,
    excluded_prefixes: Iterable[str] = (),
    excluded_dir_names: Iterable[str] = DEFAULT_EXCLUDED_DIR_NAMES,
    root_excluded_dir_names: Iterable[str] = DEFAULT_ROOT_EXCLUDED_DIR_NAMES,
) -> Iterator[Path]:
    repo = validate_repository_root(root)
    prefixes = _normalized_prefixes(excluded_prefixes)
    excluded_names = frozenset(excluded_dir_names)
    root_excluded_names = frozenset(root_excluded_dir_names)

    def fail_walk(error: OSError) -> None:
        raise RepositorySourceError("failed to walk repository sources") from error

    for directory, dirnames, filenames in os.walk(
        repo,
        topdown=True,
        onerror=fail_walk,
        followlinks=False,
    ):
        base = Path(directory)
        at_root = base == repo
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not name.startswith(".")
            and name not in excluded_names
            and not (at_root and name in root_excluded_names)
            and not (base / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = base / filename
            if not filename.endswith(".py") or path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(repo).as_posix()
            if relative.startswith(prefixes):
                continue
            yield path


def read_utf8_source(path: Path) -> str:
    if not isinstance(path, Path):
        raise ValueError("source path must be a path")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RepositorySourceError(f"failed to read UTF-8 source: {path.as_posix()}") from exc
