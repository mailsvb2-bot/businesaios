from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

RUNTIME_RELEASE_EXCLUDE_DIR_NAMES = {
    '.git',
    '.github',
    '.githooks',
    '.venv',
    'venv',
    '.release_tmp',
    '.release_build',
    '.runtime',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    'htmlcov',
    'build',
    'dist',
    'artifacts',
}

RUNTIME_RELEASE_EXCLUDE_PREFIXES = {
    'tests/',
    'docs/',
    'examples/',
    'scripts/',
    'ci/',
    '.github/',
    '.githooks/',
    'artifacts/ci/',
}

RUNTIME_RELEASE_EXCLUDE_EXACT = {
    '.coverage',
    '.DS_Store',
    'gitignore',
}

RUNTIME_RELEASE_EXCLUDE_SUFFIXES = {
    '.pyc',
    '.pyo',
    '.pyd',
    '.so',
    '.dylib',
    '.dll',
    '.db',
    '.sqlite',
    '.sqlite3',
    '.db-wal',
    '.db-shm',
    '.sqlite-wal',
    '.sqlite-shm',
    '.sqlite3-wal',
    '.sqlite3-shm',
    '.lock',
    '.log',
    '.exit',
    '.zip',
}

RUNTIME_RELEASE_EXCLUDE_GLOBS = (
    '*.coverage',
    'coverage.xml',
)


def _matches_glob(rel: str) -> bool:
    rel_path = Path(rel)
    return any(rel_path.match(pattern) for pattern in RUNTIME_RELEASE_EXCLUDE_GLOBS)


MUTABLE_RUNTIME_RELEASE_PREFIXES = (
    "data/",
    "artifacts/",
    ".runtime/",
)

MUTABLE_RUNTIME_RELEASE_EXACT = {
    "security/process_owner_security_audit.jsonl",
}


def is_runtime_release_excluded(rel: str, path: Path) -> bool:
    if rel in MUTABLE_RUNTIME_RELEASE_EXACT:
        return True
    if rel.startswith(MUTABLE_RUNTIME_RELEASE_PREFIXES):
        return True
    normalized = rel.replace('\\', '/')
    if normalized in RUNTIME_RELEASE_EXCLUDE_EXACT:
        return True
    if any(normalized.startswith(prefix) for prefix in RUNTIME_RELEASE_EXCLUDE_PREFIXES):
        return True
    if any(part in RUNTIME_RELEASE_EXCLUDE_DIR_NAMES for part in Path(normalized).parts):
        return True
    if path.suffix in RUNTIME_RELEASE_EXCLUDE_SUFFIXES:
        return True
    if _matches_glob(normalized):
        return True
    return False



def iter_runtime_release_files(root: Path) -> Iterable[Path]:
    root = Path(root).resolve()
    for path in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if is_runtime_release_excluded(rel, path):
            continue
        yield path
