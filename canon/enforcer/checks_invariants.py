from __future__ import annotations

from pathlib import Path

from canon.enforcer.rules import (
    FORBIDDEN_SECOND_BRAIN_FILE_HINTS,
    REPO_ROOT,
    SYNONYM_NAMESPACE_PAIRS,
    iter_py_files,
    relative_path,
)
from canon.repository_sources import RepositorySourceError, read_utf8_source


def check_required_invariants(report, root: Path = REPO_ROOT) -> None:
    required = [
        "core/ai/decision_core.py",
        "runtime/executor.py",
        "runtime/guard.py",
        "runtime/platform",
        "interfaces",
    ]
    for rel in required:
        if not (root / rel).exists():
            report.add(
                severity="critical",
                kind="missing-invariant",
                path=rel,
                line=None,
                message=f"Required canonical path missing: {rel}",
                hint="Restore canonical architecture before further changes.",
            )


def check_second_brain_file_hints(
    report,
    root: Path = REPO_ROOT,
    *,
    source_files: tuple[Path, ...] | None = None,
) -> None:
    paths = source_files if source_files is not None else tuple(iter_py_files(root))
    for path in paths:
        if path.name in FORBIDDEN_SECOND_BRAIN_FILE_HINTS:
            report.add(
                severity="high",
                kind="second-brain-file",
                path=relative_path(root, path),
                line=None,
                message=f"Suspicious second-brain file detected: {path.name}",
                hint="Merge this role into DecisionCore or convert it into proposal-only logic.",
            )


def _namespace_role(report, root: Path, relative: str) -> str:
    marker = root / relative / "CANON_NAMESPACE_ROLE.md"
    if not marker.exists():
        return ""
    try:
        return read_utf8_source(marker).strip()
    except RepositorySourceError as exc:
        report.add(
            severity="high",
            kind="unreadable-namespace-role",
            path=f"{relative}/CANON_NAMESPACE_ROLE.md",
            line=None,
            message=str(exc),
            hint="Restore a readable UTF-8 namespace role marker.",
        )
        return ""


def _namespace_count(source_files: tuple[Path, ...], root: Path, prefix: str) -> int:
    normalized = prefix.rstrip("/") + "/"
    return sum(
        1
        for path in source_files
        if path.name != "__init__.py" and relative_path(root, path).startswith(normalized)
    )


def check_synonym_namespaces(
    report,
    root: Path = REPO_ROOT,
    *,
    source_files: tuple[Path, ...] | None = None,
) -> None:
    paths = source_files if source_files is not None else tuple(iter_py_files(root))
    for left, right in SYNONYM_NAMESPACE_PAIRS:
        left_path = root / left
        right_path = root / right
        if not (left_path.exists() and right_path.exists()):
            continue
        left_role = _namespace_role(report, root, left)
        right_role = _namespace_role(report, root, right)
        if left_role and right_role and left_role != right_role:
            continue
        left_count = _namespace_count(paths, root, left)
        right_count = _namespace_count(paths, root, right)
        if left_count == 0 or right_count == 0:
            continue
        severity = "high" if left == "core/policy" and right == "core/policies" else "medium"
        report.add(
            severity=severity,
            kind="synonym-namespace",
            path=f"{left} <-> {right}",
            line=None,
            message=f"Competing namespace roots detected (left={left_count}, right={right_count}).",
            hint="Keep one canonical namespace and migrate imports or document explicit ownership.",
        )
