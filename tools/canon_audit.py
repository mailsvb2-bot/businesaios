from __future__ import annotations

"""Operational Canon audit for BusinesAIOS CI gates.

This module is intentionally stdlib-only and read-only: it scans repository
source files for hard architectural regressions without importing runtime code.
It backs ``python -m scripts.ci.cli --gate full|release`` through
``scripts.ci.step_canon_audit``.

Staging contract:
- hard-fail only on P0 structural regressions that make the canonical runtime
  impossible to reason about;
- report older architectural debt as bounded warnings so the server console is
  usable during alpha/staging repair waves;
- never print unbounded per-file output.
"""

import ast
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

CANON_AUDIT_TOOL_VERSION = "2026-05-11.p2"
MAX_REPORTED_ITEMS = 25

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
    violation_total: int = 0
    warning_total: int = 0

    def format_text(self) -> str:
        lines = [
            f"canon_audit version={self.version}",
            f"passed={self.passed} score={self.admission_score_100} checked_files={self.checked_files}",
            f"violations={self.violation_total} warnings={self.warning_total}",
        ]
        for item in self.violations[:MAX_REPORTED_ITEMS]:
            lines.append(f"VIOLATION {item.code} {item.path}: {item.message}")
        if self.violation_total > len(self.violations):
            lines.append(f"VIOLATION output truncated: {self.violation_total - len(self.violations)} more")
        for item in self.warnings[:MAX_REPORTED_ITEMS]:
            lines.append(f"WARNING {item.code} {item.path}: {item.message}")
        if self.warning_total > len(self.warnings):
            lines.append(f"WARNING output truncated: {self.warning_total - len(self.warnings)} more")
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


def _append_bounded(items: list[CanonViolation], item: CanonViolation) -> None:
    if len(items) < MAX_REPORTED_ITEMS:
        items.append(item)


def _check_mandatory_files(root: Path, violations: list[CanonViolation]) -> int:
    total = 0
    for rel in MANDATORY_FILES:
        if not (root / rel).exists():
            total += 1
            _append_bounded(violations, CanonViolation("CANON_MISSING_FILE", rel, "mandatory canon/runtime/CI file is missing"))
    return total


def _check_decision_core_presence(root: Path, violations: list[CanonViolation], warnings: list[CanonViolation]) -> tuple[int, int]:
    canonical = "core/ai/decision_core.py"
    canonical_path = root / canonical
    if not canonical_path.exists():
        _append_bounded(violations, CanonViolation("CANON_DECISION_CORE_MISSING", canonical, "canonical DecisionCore file is missing"))
        return 1, 0

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

    if canonical not in classes:
        _append_bounded(violations, CanonViolation("CANON_DECISION_CORE_CLASS_MISSING", canonical, "canonical file must define class DecisionCore"))
        return 1, 0

    extras = sorted(rel for rel in classes if rel != canonical)
    if extras:
        _append_bounded(
            warnings,
            CanonViolation(
                "CANON_DECISION_CORE_EXTRA_MATCHES",
                ",".join(extras[:8]),
                "extra DecisionCore class name matches found; keep them non-runtime or collapse in a negative-mass wave",
            ),
        )
        return 0, len(extras)
    return 0, 0


def _check_private_internal_imports(root: Path, warnings: list[CanonViolation]) -> int:
    total = 0
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
                    total += 1
                    _append_bounded(
                        warnings,
                        CanonViolation(
                            "CANON_PRIVATE_EFFECTS_IMPORT",
                            rel,
                            f"runtime._internal import should route through executor/effects sealed gateway: {module}",
                        ),
                    )
    return total


def _check_raw_side_effect_imports(root: Path, warnings: list[CanonViolation]) -> int:
    total = 0
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
                    total += 1
                    _append_bounded(
                        warnings,
                        CanonViolation(
                            "CANON_RAW_SIDE_EFFECT_IMPORT",
                            rel,
                            f"raw external/side-effect import '{root_name}' is outside sealed effects/CI/dev allow-list",
                        ),
                    )
    return total


def _check_guarded_execution_markers(root: Path, violations: list[CanonViolation]) -> int:
    total = 0
    executor_text = (root / "runtime/executor.py").read_text(encoding="utf-8") if (root / "runtime/executor.py").exists() else ""
    guard_text = (root / "runtime/guard.py").read_text(encoding="utf-8") if (root / "runtime/guard.py").exists() else ""
    required_executor = ("class RuntimeExecutor", "def execute", "execute_core_flow", "preflight_and_verify")
    required_guard = ("class RuntimeGuard", "def verify", "def execute_once")
    for marker in required_executor:
        if marker not in executor_text:
            total += 1
            _append_bounded(violations, CanonViolation("CANON_EXECUTOR_MARKER_MISSING", "runtime/executor.py", f"missing marker: {marker}"))
    for marker in required_guard:
        if marker not in guard_text:
            total += 1
            _append_bounded(violations, CanonViolation("CANON_GUARD_MARKER_MISSING", "runtime/guard.py", f"missing marker: {marker}"))
    return total


def _check_admin_surface_advisory(root: Path, warnings: list[CanonViolation]) -> int:
    matched = False
    for path in _iter_py_files(root):
        rel = _rel(root, path).lower()
        if any(marker in rel for marker in ADVISORY_ADMIN_MARKERS):
            matched = True
            break
    if not matched:
        _append_bounded(
            warnings,
            CanonViolation(
                "CANON_ADMIN_SURFACE_NOT_DISCOVERED",
                ".",
                "no admin/control-plane/operator Python surface discovered by path; new features must be visible to operators",
            ),
        )
        return 1
    return 0


def run_operational_canon_checks(root: Path | str) -> CanonAuditReport:
    repo_root = Path(root).resolve()
    violations: list[CanonViolation] = []
    warnings: list[CanonViolation] = []

    violation_total = 0
    warning_total = 0

    violation_total += _check_mandatory_files(repo_root, violations)
    if violation_total == 0:
        v, w = _check_decision_core_presence(repo_root, violations, warnings)
        violation_total += v
        warning_total += w
        violation_total += _check_guarded_execution_markers(repo_root, violations)
        # Staging-safe: legacy debt is reported, not made a surprise hard-fail.
        # Dedicated architecture tests can still hard-fail known locked rules.
        warning_total += _check_private_internal_imports(repo_root, warnings)
        warning_total += _check_raw_side_effect_imports(repo_root, warnings)
        warning_total += _check_admin_surface_advisory(repo_root, warnings)

    checked_files = sum(1 for _ in _iter_py_files(repo_root))
    penalty = min(100, violation_total * 25 + min(warning_total, 10) * 2)
    score = max(0, 100 - penalty)
    return CanonAuditReport(
        passed=violation_total == 0,
        admission_score_100=score,
        violations=tuple(violations),
        warnings=tuple(warnings),
        checked_files=checked_files,
        violation_total=violation_total,
        warning_total=warning_total,
    )


__all__ = [
    "CANON_AUDIT_TOOL_VERSION",
    "CanonAuditReport",
    "CanonViolation",
    "run_operational_canon_checks",
]
