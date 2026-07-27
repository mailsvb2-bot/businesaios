from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterable

CANON_BOUNDED_REPOSITORY_SOURCE_SCAN = True

_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "artifacts",
        "build",
        "coverage_html",
        "dist",
        "env",
        "htmlcov",
        "node_modules",
        "runtime_data",
        "site-packages",
        "tmp",
        "venv",
    }
)
_DEFAULT_MAX_SOURCE_BYTES = 4 * 1024 * 1024


def iter_repository_python_files(
    root: Path,
    *,
    excluded_directory_names: Iterable[str] = _EXCLUDED_DIRECTORY_NAMES,
) -> tuple[Path, ...]:
    """Return regular in-tree Python files without following symlinks.

    The iterative scandir traversal avoids the unbounded `Path.rglob` behavior
    that can descend into virtual environments, extracted artifacts, mounted
    runtime data, or symlink cycles during architecture collection.
    """

    resolved_root = root.resolve()
    excluded = frozenset(str(name) for name in excluded_directory_names)
    files: list[Path] = []
    pending = [resolved_root]
    while pending:
        directory = pending.pop()
        try:
            entries = tuple(os.scandir(directory))
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
            continue
        for entry in entries:
            if entry.name in excluded:
                continue
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if entry.name.endswith(".py"):
                files.append(Path(entry.path))
    return tuple(sorted(files))


def read_python_source(
    path: Path,
    *,
    max_bytes: int = _DEFAULT_MAX_SOURCE_BYTES,
) -> str:
    """Read one bounded regular Python source file as UTF-8."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"not a regular source file: {path}")
    if info.st_size > max_bytes:
        raise ValueError(
            f"source file exceeds {max_bytes} bytes: {path} ({info.st_size})"
        )
    with path.open("rb") as handle:
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"source file exceeds {max_bytes} bytes: {path}")
    return payload.decode("utf-8")


__all__ = [
    "CANON_BOUNDED_REPOSITORY_SOURCE_SCAN",
    "iter_repository_python_files",
    "read_python_source",
]
