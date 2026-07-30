from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Iterable
from pathlib import Path

DELIVERY_SCAN_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)


def _pathspec_variants(pathspec: str) -> tuple[str, ...]:
    normalized = pathspec.strip().replace("\\", "/")
    if not normalized:
        return ()

    variants = {normalized}
    pending = [normalized]
    while pending:
        candidate = pending.pop()
        marker = "/**/"
        if marker not in candidate:
            continue
        collapsed = candidate.replace(marker, "/", 1)
        if collapsed not in variants:
            variants.add(collapsed)
            pending.append(collapsed)
    return tuple(sorted(variants))


def _matches_pathspec(relative_path: str, pathspec: str) -> bool:
    normalized = pathspec.strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return True
    if not any(token in normalized for token in ("*", "?", "[")):
        return relative_path == normalized or relative_path.startswith(f"{normalized}/")
    return any(
        fnmatch.fnmatchcase(relative_path, variant)
        for variant in _pathspec_variants(normalized)
    )


def _delivery_files(
    root: Path,
    *,
    pathspecs: tuple[str, ...],
    excluded_dirs: frozenset[str],
) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if excluded_dirs.intersection(relative.parts):
            continue
        relative_posix = relative.as_posix()
        if pathspecs and not any(
            _matches_pathspec(relative_posix, pathspec) for pathspec in pathspecs
        ):
            continue
        files.append(path)
    return tuple(files)


def tracked_files(
    root: Path,
    *pathspecs: str,
    fallback_excluded_dirs: Iterable[str] = DELIVERY_SCAN_EXCLUDED_DIRS,
) -> tuple[Path, ...]:
    """Return tracked files, or delivery-tree files when Git metadata is unavailable.

    Source checkouts use ``git ls-files``. ZIP/source distributions do not contain
    ``.git`` metadata, so a failed Git query falls back to a deterministic filesystem
    scan with the same path filters. This keeps packaging tests meaningful instead of
    crashing with ``CalledProcessError``.
    """

    root = Path(root)
    command = ["git", "ls-files", "-z", *pathspecs]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _delivery_files(
            root,
            pathspecs=tuple(pathspecs),
            excluded_dirs=frozenset(fallback_excluded_dirs),
        )

    files: list[Path] = []
    for raw in result.stdout.decode("utf-8", errors="ignore").split("\0"):
        if not raw:
            continue
        path = root / raw
        if path.is_file():
            files.append(path)
    return tuple(files)
