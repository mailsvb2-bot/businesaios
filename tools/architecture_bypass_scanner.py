"""Canonical repository-wide architecture bypass scanner.

This module owns repository discovery and generic raw-effect checks. Decision
authority semantics have one owner in
``tools.decision_authority_indirect_scanner`` and are delegated here so legacy
scanner callers keep the same public surface without a second rule engine.
"""

from __future__ import annotations

import ast
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from canon.anti_second_brain_rules import (
    CANONICAL_DECISION_OWNER_PREFIXES,
    DECISION_AUTHORITY_METHODS,
    is_canonical_decision_owner_path,
)
from tools.decision_authority_indirect_scanner import (
    _scan_ast as _scan_decision_authority_ast,
)

CANON_ARCHITECTURE_BYPASS_SCANNER = True
CANON_SCAN_ALL_SOURCE_ROOTS = True
CANON_DELEGATES_DECISION_AUTHORITY_SCAN = True

GLOBAL_EXCLUDED_DIRS = {
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
ROOT_EXCLUDED_DIRS = {
    "artifacts",
    "build",
    "data",
    "dist",
    "htmlcov",
    "release_dist",
    "reports",
}
# Compatibility export. Discovery applies ROOT_EXCLUDED_DIRS only at repo root.
EXCLUDED_DIRS = GLOBAL_EXCLUDED_DIRS | ROOT_EXCLUDED_DIRS
SCAN_ROOTS: tuple[str, ...] = ()
TEST_OR_SCRIPT_PREFIXES = ("tests/", "scripts/")
APPROVED_RAW_EFFECT_PREFIXES = (
    "runtime/_internal/",
    "runtime/execution/",
    "runtime/platform/",
    "runtime/handlers/",
    "storage/",
    "observability/platform/",
    "adapters/",
    "entrypoints/",
)
APPROVED_DYNAMIC_IMPORT_FILES = {
    "runtime/handler_loader.py",
    "runtime/boot/actions_registry.py",
    "runtime/boot/registration_manifest.py",
    "runtime/marketing/__init__.py",
    "runtime/boot/__init__.py",
    "application/decision_state/__init__.py",
    "observability/__init__.py",
}
APPROVED_SYSTEM_EXIT_FILES = {"scripts/ci/cli.py"}
TEXT_DENY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "unsafe_requests_verify_false",
        re.compile(r"\bverify\s*=\s*False\b"),
    ),
    (
        "unsafe_shell_true",
        re.compile(r"\bshell\s*=\s*True\b"),
    ),
    (
        "raw_os_system",
        re.compile(r"\bos\.system\s*\("),
    ),
    (
        "raw_subprocess_popen",
        re.compile(r"\bsubprocess\.Popen\s*\("),
    ),
    (
        "raw_eval_exec",
        re.compile(r"(?<![\w.])(eval|exec)\s*\("),
    ),
)
RAW_SIDE_EFFECT_CALLS = {
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "patch"),
    ("requests", "delete"),
    ("httpx", "get"),
    ("httpx", "post"),
    ("httpx", "put"),
    ("httpx", "patch"),
    ("httpx", "delete"),
    ("subprocess", "run"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
}
DECISION_BYPASS_CALLS = DECISION_AUTHORITY_METHODS
APPROVED_DECISION_OWNER_PREFIXES = CANONICAL_DECISION_OWNER_PREFIXES
_DECISION_FINDING_CODE_MAP = {
    "decision_authority_alias_import": (
        "decision_authority_alias_import_outside_owner"
    ),
    "decision_authority_name_reference": (
        "decision_authority_name_reference_outside_owner"
    ),
    "decision_authority_method_reference": (
        "decision_authority_reference_outside_owner"
    ),
    "decision_authority_mapping_lookup": (
        "subscript_decision_authority_lookup_outside_owner"
    ),
    "decision_authority_mapping_mutation": (
        "dynamic_decision_authority_mutation_outside_owner"
    ),
    "decision_authority_call": "possible_decision_core_bypass",
    "decision_authority_dynamic_lookup": (
        "dynamic_decision_authority_lookup_outside_owner"
    ),
    "decision_authority_dynamic_mutation": (
        "dynamic_decision_authority_mutation_outside_owner"
    ),
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.detail}"


def _is_excluded(path: Path) -> bool:
    """Compatibility helper for callers testing the exported exclusion set."""

    return any(part in EXCLUDED_DIRS for part in path.parts)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        base = Path(directory)
        at_root = not base.relative_to(root).parts
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in GLOBAL_EXCLUDED_DIRS
            and not (at_root and name in ROOT_EXCLUDED_DIRS)
        )
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield base / filename


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test_or_script(rel: str) -> bool:
    return rel.startswith(TEST_OR_SCRIPT_PREFIXES)


def _is_approved_raw_effect(rel: str) -> bool:
    return rel.startswith(
        APPROVED_RAW_EFFECT_PREFIXES
    ) or _is_test_or_script(rel)


def _is_approved_decision_owner(rel: str) -> bool:
    return is_canonical_decision_owner_path(rel)


def _expression_path(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expression_path(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        base = _expression_path(node.func)
        argument = ""
        if node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(
                first.value,
                str,
            ):
                argument = repr(first.value)
            else:
                argument = _expression_path(first)
        return f"{base}({argument})" if base else f"({argument})"
    if isinstance(node, ast.Subscript):
        base = _expression_path(node.value)
        return f"{base}[]" if base else "[]"
    return ""


def _call_name(node: ast.AST) -> tuple[str | None, str | None]:
    if isinstance(node, ast.Attribute):
        owner = _expression_path(node.value)
        return owner or None, node.attr
    if isinstance(node, ast.Name):
        return None, node.id
    return None, None


def _root_owner(owner: str | None) -> str | None:
    if not owner:
        return None
    return owner.split(".", 1)[0].removesuffix("()").removesuffix("[]")


def _scan_text(
    *,
    root: Path,
    path: Path,
    rel: str,
    text: str,
) -> list[Finding]:
    del root, path
    findings: list[Finding] = []
    if _is_test_or_script(rel):
        return findings
    lines = text.splitlines()
    for code, pattern in TEXT_DENY_RULES:
        if code == "raw_eval_exec" and rel in APPROVED_DYNAMIC_IMPORT_FILES:
            continue
        if code in {
            "raw_os_system",
            "raw_subprocess_popen",
            "unsafe_shell_true",
        } and _is_approved_raw_effect(rel):
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(
                    Finding(
                        code=code,
                        path=rel,
                        line=lineno,
                        detail=line.strip()[:180],
                    )
                )
    return findings


def _delegated_decision_findings(
    *,
    rel: str,
    tree: ast.AST,
) -> list[Finding]:
    return [
        Finding(
            code=_DECISION_FINDING_CODE_MAP.get(item.code, item.code),
            path=item.path,
            line=item.line,
            detail=item.detail,
        )
        for item in _scan_decision_authority_ast(rel=rel, tree=tree)
    ]


def _scan_ast(
    *,
    root: Path,
    path: Path,
    rel: str,
    tree: ast.AST,
) -> list[Finding]:
    del root, path
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        owner, name = _call_name(node.func)
        line = int(getattr(node, "lineno", 0) or 0)
        raw_owner = _root_owner(owner)
        if (
            raw_owner is not None
            and name is not None
            and (raw_owner, name) in RAW_SIDE_EFFECT_CALLS
            and not _is_approved_raw_effect(rel)
        ):
            findings.append(
                Finding(
                    code="raw_side_effect_call_outside_owner",
                    path=rel,
                    line=line,
                    detail=(
                        f"{owner}.{name}() must be routed through approved "
                        "effects/provider owners"
                    ),
                )
            )
        if (
            owner is None
            and name == "__import__"
            and rel not in APPROVED_DYNAMIC_IMPORT_FILES
            and not _is_test_or_script(rel)
        ):
            findings.append(
                Finding(
                    code="dynamic_import_outside_owner",
                    path=rel,
                    line=line,
                    detail=(
                        "__import__() outside approved loader/registry surface"
                    ),
                )
            )
        if (
            owner is None
            and name == "exit"
            and rel not in APPROVED_SYSTEM_EXIT_FILES
            and not _is_test_or_script(rel)
        ):
            findings.append(
                Finding(
                    code="raw_process_exit_outside_ci_owner",
                    path=rel,
                    line=line,
                    detail="exit() outside approved CI owner surface",
                )
            )

    findings.extend(
        _delegated_decision_findings(rel=rel, tree=tree)
    )
    return findings


def scan(root: Path | None = None) -> tuple[Finding, ...]:
    repo = (root or Path.cwd()).resolve()
    findings: list[Finding] = []
    for path in _iter_python_files(repo):
        rel = _rel(repo, path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                Finding(
                    code="non_utf8_python_file",
                    path=rel,
                    line=0,
                    detail="file is not utf-8 decodable",
                )
            )
            continue
        findings.extend(
            _scan_text(root=repo, path=path, rel=rel, text=text)
        )
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            findings.append(
                Finding(
                    code="syntax_error",
                    path=rel,
                    line=int(exc.lineno or 0),
                    detail=str(exc),
                )
            )
            continue
        findings.extend(
            _scan_ast(
                root=repo,
                path=path,
                rel=rel,
                tree=tree,
            )
        )
    unique = {
        (item.code, item.path, item.line, item.detail): item
        for item in findings
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.path,
                item.line,
                item.code,
                item.detail,
            ),
        )
    )


def main() -> int:
    findings = scan(Path.cwd())
    if not findings:
        print("architecture bypass scanner passed")
        return 0
    print(f"architecture bypass scanner failed: findings={len(findings)}")
    for finding in findings[:80]:
        print(finding.format())
    if len(findings) > 80:
        print(f"... {len(findings) - 80} more finding(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
