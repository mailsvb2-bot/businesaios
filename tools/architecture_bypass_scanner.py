"""Canonical repository-wide architecture bypass scanner.

The scanner checks Python source while pruning generated, cache, dependency,
report, and mutable-state trees. Source discovery is repository-wide so a new
product package cannot fall outside the canonical checks by accident.
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
    CONTEXTUAL_DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_RECEIVER_TOKENS,
    HARD_DECISION_AUTHORITY_METHODS,
)

CANON_ARCHITECTURE_BYPASS_SCANNER = True
CANON_SCAN_ALL_SOURCE_ROOTS = True

EXCLUDED_DIRS = {
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
    "artifacts",
    "build",
    "data",
    "dist",
    "htmlcov",
    "node_modules",
    "release_dist",
    "reports",
    "target",
    "venv",
}

SCAN_ROOTS: tuple[str, ...] = ()

TEST_OR_SCRIPT_PREFIXES = (
    "tests/",
    "scripts/",
)

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

APPROVED_SYSTEM_EXIT_FILES = {
    "scripts/ci/cli.py",
}

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


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.detail}"


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        base = Path(directory)
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = base / filename
            relative = path.relative_to(root)
            if not _is_excluded(relative):
                yield path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test_or_script(rel: str) -> bool:
    return rel.startswith(TEST_OR_SCRIPT_PREFIXES)


def _is_approved_raw_effect(rel: str) -> bool:
    return rel.startswith(APPROVED_RAW_EFFECT_PREFIXES) or _is_test_or_script(rel)


def _is_approved_decision_owner(rel: str) -> bool:
    return rel.startswith(APPROVED_DECISION_OWNER_PREFIXES)


def _expression_path(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expression_path(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        base = _expression_path(node.func)
        return f"{base}()" if base else "()"
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


def _normalized_receiver(owner: str | None) -> str:
    return "".join(ch for ch in str(owner or "").casefold() if ch.isalnum())


def _receiver_looks_like_decision_authority(owner: str | None) -> bool:
    normalized = _normalized_receiver(owner)
    return any(token in normalized for token in DECISION_AUTHORITY_RECEIVER_TOKENS)


def _is_possible_decision_bypass(owner: str | None, name: str | None) -> bool:
    if name not in DECISION_BYPASS_CALLS:
        return False
    if name in HARD_DECISION_AUTHORITY_METHODS:
        return True
    if name in CONTEXTUAL_DECISION_AUTHORITY_METHODS:
        return _receiver_looks_like_decision_authority(owner)
    return False


def _scan_text(*, root: Path, path: Path, rel: str, text: str) -> list[Finding]:
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


def _scan_ast(*, root: Path, path: Path, rel: str, tree: ast.AST) -> list[Finding]:
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
                    detail="__import__() outside approved loader/registry surface",
                )
            )
        if _is_possible_decision_bypass(owner, name) and not _is_approved_decision_owner(rel):
            target = f"{owner}.{name}" if owner else str(name)
            findings.append(
                Finding(
                    code="possible_decision_core_bypass",
                    path=rel,
                    line=line,
                    detail=f"{target}() outside DecisionCore/gateway owner path",
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
        findings.extend(_scan_text(root=repo, path=path, rel=rel, text=text))
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
        findings.extend(_scan_ast(root=repo, path=path, rel=rel, tree=tree))
    return tuple(sorted(findings, key=lambda item: (item.path, item.line, item.code)))


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
