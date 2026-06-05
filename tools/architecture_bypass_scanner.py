from __future__ import annotations

"""Canonical repo-wide architecture bypass scanner.

The scanner is intentionally conservative: it fails only on high-confidence
patterns that create raw side effects, hidden execution paths, or unsafe runtime
bypasses outside approved owner surfaces. It is not a replacement for the full
canon audit; it is a small, deterministic CI guard that keeps new code from
reintroducing obvious second-brain / raw-effect paths.
"""

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CANON_ARCHITECTURE_BYPASS_SCANNER = True

EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "data",
    "htmlcov",
    "node_modules",
    "release_dist",
}

SCAN_ROOTS = (
    "adapters",
    "application",
    "bootstrap",
    "core",
    "entrypoints",
    "governance",
    "learning",
    "observability",
    "runtime",
    "scripts",
    "storage",
    "tools",
)

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

DECISION_BYPASS_CALLS = {
    "decide",
    "issue",
    "optimize",
}

APPROVED_DECISION_OWNER_PREFIXES = (
    "core/ai/",
    "application/decision_runtime/",
    "runtime/decision_gateway.py",
    "runtime/decision_path_lock.py",
    "tests/",
)


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
    for prefix in SCAN_ROOTS:
        base = root / prefix
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root)
            if not _is_excluded(rel):
                yield path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test_or_script(rel: str) -> bool:
    return rel.startswith(TEST_OR_SCRIPT_PREFIXES)


def _is_approved_raw_effect(rel: str) -> bool:
    return rel.startswith(APPROVED_RAW_EFFECT_PREFIXES) or _is_test_or_script(rel)


def _is_approved_decision_owner(rel: str) -> bool:
    return rel.startswith(APPROVED_DECISION_OWNER_PREFIXES)


def _call_name(node: ast.AST) -> tuple[str | None, str | None]:
    if isinstance(node, ast.Attribute):
        owner = node.value
        if isinstance(owner, ast.Name):
            return owner.id, node.attr
    if isinstance(node, ast.Name):
        return None, node.id
    return None, None


def _scan_text(*, root: Path, path: Path, rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if _is_test_or_script(rel):
        return findings
    lines = text.splitlines()
    for code, pattern in TEXT_DENY_RULES:
        if code == "raw_eval_exec" and rel in APPROVED_DYNAMIC_IMPORT_FILES:
            continue
        if code in {"raw_os_system", "raw_subprocess_popen", "unsafe_shell_true"} and _is_approved_raw_effect(rel):
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(Finding(code=code, path=rel, line=lineno, detail=line.strip()[:180]))
    return findings


def _scan_ast(*, root: Path, path: Path, rel: str, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        owner, name = _call_name(node.func)
        line = int(getattr(node, "lineno", 0) or 0)
        if owner is not None and name is not None and (owner, name) in RAW_SIDE_EFFECT_CALLS and not _is_approved_raw_effect(rel):
            findings.append(
                Finding(
                    code="raw_side_effect_call_outside_owner",
                    path=rel,
                    line=line,
                    detail=f"{owner}.{name}() must be routed through approved effects/provider owners",
                )
            )
        if owner is None and name == "__import__" and rel not in APPROVED_DYNAMIC_IMPORT_FILES and not _is_test_or_script(rel):
            findings.append(
                Finding(
                    code="dynamic_import_outside_owner",
                    path=rel,
                    line=line,
                    detail="__import__() outside approved loader/registry surface",
                )
            )
        if owner is not None and name in DECISION_BYPASS_CALLS and not _is_approved_decision_owner(rel):
            if owner not in {"self", "super"}:
                findings.append(
                    Finding(
                        code="possible_decision_core_bypass",
                        path=rel,
                        line=line,
                        detail=f"{owner}.{name}() outside DecisionCore/gateway owner path",
                    )
                )
        if owner is None and name == "exit" and rel not in APPROVED_SYSTEM_EXIT_FILES and not _is_test_or_script(rel):
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
            findings.append(Finding(code="non_utf8_python_file", path=rel, line=0, detail="file is not utf-8 decodable"))
            continue
        findings.extend(_scan_text(root=repo, path=path, rel=rel, text=text))
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            findings.append(Finding(code="syntax_error", path=rel, line=int(exc.lineno or 0), detail=str(exc)))
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
