from __future__ import annotations

"""Operational Canon audit for BusinesAIOS CI gates.

This module is intentionally stdlib-only and read-only: it scans repository
source files for hard architectural regressions without importing runtime code.
It backs ``python -m scripts.ci.cli --gate full|release`` through
``scripts.ci.step_canon_audit``.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CANON_AUDIT_TOOL_VERSION = "2026-05-11.p0"

PY_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
    "node_modules",
    "reports",
}

MANDATORY_FILES = (
    "docs/SYSTEM_TZ_CANONICAL.md",
    "core/ai/decision_core.py",
    "core/decision_core.py",
    "runtime/executor.py",
    "runtime/guard.py",
    "runtime/_internal/_effects_impl.py",
    "scripts/ci/step_canon_audit.py",
)

FORBIDDEN_SDK_IMPORTS = {
    "aiogram",
    "httpx",
    "requests",
    "socket",
    "subprocess",
    "telebot",
    "telegram",
    "urllib",
    "yookassa",
}

ALLOWED_SDK_FILES = {
    "runtime/_internal/_effects_impl.py",
    "runtime/_internal/effects_clients/http_client.py",
    "scripts/ci/subprocess_io.py",
    "tests/test_domain_fs_check_script_smoke.py",
    "tests/test_seccomp.py",
    "tests/test_world_snapshot_ast_lock.py",
}

ALLOWED_SDK_PREFIXES = (
    "runtime/_internal/effects_actions/",
    "runtime/_internal/effects_clients/",
    "scripts/ci/",
    "scripts/dev/",
    "tests/",
)

ALLOWED_RUNTIME_INTERNAL_IMPORTERS = {
    "runtime/effects.py",
    "runtime/executor.py",
    "tests/test_architecture.py",
}

ALLOWED_RUNTIME_INTERNAL_IMPORT_PREFIXES = (
    "runtime/_internal/",
    "tests/",
)

ADVISORY_ADMIN_MARKERS = (
    "admin",
    "control_plane",
    "control-plane",
    "operator",
)


@dataclass(frozen=True)
class CanonViolation:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class CanonAuditReport:
    passed: bool
    admission_score_100: int
    violations: tuple[CanonViolation, ...] = field(default_factory=tuple)
    warnings: tuple[CanonViolation, ...] = field(default_factory=tuple)
    checked_files: int = 0
    version: str = CANON_AUDIT_TOOL_VERSION

    def format_text(self) -> str:
        lines = [
            f"canon_audit version={self.version}",
            f"passed={self.passed} score={self.admission_score_100} checked_files={self.checked_files}",
            f"violations={len(self.violations)} warnings={len(self.warnings)}",
        ]
        for item in self.violations:
            lines.append(f"VIOLATION {item.code} {item.path}: {item.message}")
        for item in self.warnings:
            lines.append(f"WARNING {item.code} {item.path}: {item.message}")
        return "\n".join(lines)


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        parts = set(path.relative_to(root).parts)
        if parts.intersection(PY_SKIP_DIRS):
            continue
        yield path


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        raise
    except UnicodeDecodeError:
        return None


def _import_roots(node: ast.AST) -> list[str]:
    roots: list[str] = []
    if isinstance(node, ast.Import):
        roots.extend(alias.name.split(".")[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            roots.append(node.module.split(".")[0])
    return roots


def _import_modules(node: ast.AST) -> list[str]:
    modules: list[str] = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            modules.append(node.module)
    return modules


def _is_allowed(rel: str, *, files: set[str], prefixes: tuple[str, ...]) -> bool:
    return rel in files or rel.startswith(prefixes)


def _check_mandatory_files(root: Path, violations: list[CanonViolation]) -> None:
    for rel in MANDATORY_FILES:
        if not (root / rel).exists():
            violations.append(CanonViolation("CANON_MISSING_FILE", rel, "mandatory canon/runtime/CI file is missing"))


def _check_single_decision_core(root: Path, violations: list[CanonViolation]) -> None:
    classes: list[str] = []
    for path in _iter_py_files(root):
        rel = _rel(root, path)
        if rel.startswith("tests/"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "DecisionCore":
                classes.append(rel)
    if classes != ["core/ai/decision_core.py"]:
        violations.append(
            CanonViolation(
                "CANON_DECISION_CORE_MULTIPLE_OR_MOVED",
                ",".join(classes) or "<none>",
                "DecisionCore class must exist exactly once at core/ai/decision_core.py",
            )
        )


def _check_private_internal_imports(root: Path, violations: list[CanonViolation]) -> None:
    for path in _iter_py_files(root):
        rel = _rel(root, path)
        if _is_allowed(rel, files=ALLOWED_RUNTIME_INTERNAL_IMPORTERS, prefixes=ALLOWED_RUNTIME_INTERNAL_IMPORT_PREFIXES):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            for module in _import_modules(node):
                if module == "runtime._internal" or module.startswith("runtime._internal."):
                    violations.append(
                        CanonViolation(
                            "CANON_PRIVATE_EFFECTS_IMPORT",
                            rel,
                            f"runtime._internal import is allowed only through executor/effects sealed gateway: {module}",
                        )
                    )


def _check_raw_side_effect_imports(root: Path, violations: list[CanonViolation]) -> None:
    for path in _iter_py_files(root):
        rel = _rel(root, path)
        if rel.startswith("tests/"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            for root_name in _import_roots(node):
                if root_name in FORBIDDEN_SDK_IMPORTS and not _is_allowed(
                    rel,
                    files=ALLOWED_SDK_FILES,
                    prefixes=ALLOWED_SDK_PREFIXES,
                ):
                    violations.append(
                        CanonViolation(
                            "CANON_RAW_SIDE_EFFECT_IMPORT",
                            rel,
                            f"raw external/side-effect import '{root_name}' is outside sealed effects/CI/dev allow-list",
                        )
                    )


def _check_guarded_execution_markers(root: Path, violations: list[CanonViolation]) -> None:
    executor_text = (root / "runtime/executor.py").read_text(encoding="utf-8") if (root / "runtime/executor.py").exists() else ""
    guard_text = (root / "runtime/guard.py").read_text(encoding="utf-8") if (root / "runtime/guard.py").exists() else ""
    required_executor = ("class RuntimeExecutor", "def execute", "execute_core_flow", "preflight_and_verify")
    required_guard = ("class RuntimeGuard", "def verify", "def execute_once")
    for marker in required_executor:
        if marker not in executor_text:
            violations.append(CanonViolation("CANON_EXECUTOR_MARKER_MISSING", "runtime/executor.py", f"missing marker: {marker}"))
    for marker in required_guard:
        if marker not in guard_text:
            violations.append(CanonViolation("CANON_GUARD_MARKER_MISSING", "runtime/guard.py", f"missing marker: {marker}"))


def _check_admin_surface_advisory(root: Path, warnings: list[CanonViolation]) -> None:
    matched = False
    for path in _iter_py_files(root):
        rel = _rel(root, path).lower()
        if any(marker in rel for marker in ADVISORY_ADMIN_MARKERS):
            matched = True
            break
    if not matched:
        warnings.append(
            CanonViolation(
                "CANON_ADMIN_SURFACE_NOT_DISCOVERED",
                ".",
                "no admin/control-plane/operator Python surface discovered by path; new features must be visible to operators",
            )
        )


def run_operational_canon_checks(root: Path | str) -> CanonAuditReport:
    repo_root = Path(root).resolve()
    violations: list[CanonViolation] = []
    warnings: list[CanonViolation] = []

    _check_mandatory_files(repo_root, violations)
    if not violations:
        _check_single_decision_core(repo_root, violations)
        _check_private_internal_imports(repo_root, violations)
        _check_raw_side_effect_imports(repo_root, violations)
        _check_guarded_execution_markers(repo_root, violations)
        _check_admin_surface_advisory(repo_root, warnings)

    checked_files = sum(1 for _ in _iter_py_files(repo_root))
    penalty = min(100, len(violations) * 25 + len(warnings) * 3)
    score = max(0, 100 - penalty)
    return CanonAuditReport(
        passed=not violations,
        admission_score_100=score,
        violations=tuple(violations),
        warnings=tuple(warnings),
        checked_files=checked_files,
    )


__all__ = [
    "CANON_AUDIT_TOOL_VERSION",
    "CanonAuditReport",
    "CanonViolation",
    "run_operational_canon_checks",
]
