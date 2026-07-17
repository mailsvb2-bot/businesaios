from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

RUNTIME_RELEASE_EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",
    ".githooks",
    ".venv",
    "venv",
    ".release_tmp",
    ".release_build",
    ".runtime",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "build",
    "dist",
    "artifacts",
    "target",
}

RUNTIME_RELEASE_EXCLUDE_PREFIXES = {
    "tests/",
    "docs/",
    "examples/",
    "scripts/",
    "ci/",
    ".github/",
    ".githooks/",
    "artifacts/ci/",
    "runtime/data/",
    "reports/",
}

RUNTIME_RELEASE_EXCLUDE_EXACT = {
    ".coverage",
    ".DS_Store",
    "desktop.ini",
    "gitignore",
}

RUNTIME_RELEASE_EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".dll",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite-journal",
    ".sqlite3-wal",
    ".sqlite3-shm",
    ".sqlite3-journal",
    ".jsonl",
    ".lock",
    ".log",
    ".exit",
    ".zip",
}

RUNTIME_RELEASE_INCLUDE_FILE_NAMES = {
    "Cargo.lock",
}

RUNTIME_RELEASE_EXCLUDE_GLOBS = (
    "*.coverage",
    "coverage.xml",
)

RUNTIME_RELEASE_EXCLUDE_ROOT_GLOBS = (
    "*_REPORT*.md",
    "*_REPORT*.txt",
    "*TRIAGE*.md",
    "*TRIAGE*.txt",
)

MUTABLE_RUNTIME_RELEASE_PREFIXES = (
    "data/",
    "runtime/data/",
    "reports/",
    "artifacts/",
    ".runtime/",
)

MUTABLE_RUNTIME_RELEASE_EXACT = {
    "security/process_owner_security_audit.jsonl",
}

RUNTIME_RELEASE_REQUIRED_MEMBERS = {
    "Dockerfile",
    "VERSION",
    "main.py",
    "requirements.release.lock.txt",
    "rust/businessaios_safety_core/Cargo.lock",
}


def _matches_glob(rel: str) -> bool:
    rel_path = Path(rel)
    return any(rel_path.match(pattern) for pattern in RUNTIME_RELEASE_EXCLUDE_GLOBS)


def _matches_root_internal_report(rel: str) -> bool:
    rel_path = Path(rel)
    if len(rel_path.parts) != 1:
        return False
    return any(
        rel_path.match(pattern)
        for pattern in RUNTIME_RELEASE_EXCLUDE_ROOT_GLOBS
    )


def _normalized_member(rel: str) -> str:
    return rel.replace("\\", "/").strip()


def _unsafe_member_reason(rel: str) -> str | None:
    normalized = _normalized_member(rel)
    path = Path(normalized)
    if not normalized:
        return "empty_member"
    if rel != normalized:
        return "non_canonical_separator"
    if path.is_absolute() or normalized.startswith("/"):
        return "absolute_member"
    if any(part in {"", ".", ".."} for part in path.parts):
        return "path_traversal_member"
    return None


def is_runtime_release_excluded(rel: str, path: Path) -> bool:
    normalized = _normalized_member(rel)
    if normalized in MUTABLE_RUNTIME_RELEASE_EXACT:
        return True
    if normalized.startswith(MUTABLE_RUNTIME_RELEASE_PREFIXES):
        return True
    if normalized in RUNTIME_RELEASE_EXCLUDE_EXACT:
        return True
    if any(
        normalized.startswith(prefix)
        for prefix in RUNTIME_RELEASE_EXCLUDE_PREFIXES
    ):
        return True
    if any(
        part in RUNTIME_RELEASE_EXCLUDE_DIR_NAMES
        for part in Path(normalized).parts
    ):
        return True
    if _matches_root_internal_report(normalized):
        return True
    if path.name in RUNTIME_RELEASE_INCLUDE_FILE_NAMES:
        return False
    if path.suffix in RUNTIME_RELEASE_EXCLUDE_SUFFIXES:
        return True
    return bool(_matches_glob(normalized))


def runtime_release_member_violations(
    members: Sequence[str],
) -> tuple[str, ...]:
    violations: list[str] = []
    seen: set[str] = set()
    normalized_members: set[str] = set()

    for member in members:
        normalized = _normalized_member(member)
        reason = _unsafe_member_reason(member)
        if reason is not None:
            violations.append(f"{reason}:{member}")
            continue
        if normalized in seen:
            violations.append(f"duplicate_member:{normalized}")
            continue
        seen.add(normalized)
        normalized_members.add(normalized)
        if is_runtime_release_excluded(normalized, Path(normalized)):
            violations.append(f"excluded_member:{normalized}")

    for required in sorted(RUNTIME_RELEASE_REQUIRED_MEMBERS - normalized_members):
        violations.append(f"required_member_missing:{required}")

    return tuple(sorted(set(violations)))


def iter_runtime_release_files(root: Path) -> Iterable[Path]:
    root = Path(root).resolve()
    for path in sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if is_runtime_release_excluded(rel, path):
            continue
        yield path


__all__ = [
    "RUNTIME_RELEASE_REQUIRED_MEMBERS",
    "is_runtime_release_excluded",
    "iter_runtime_release_files",
    "runtime_release_member_violations",
]
