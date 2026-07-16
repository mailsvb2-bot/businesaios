from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


@dataclass(frozen=True)
class ForbiddenWorldModelPattern:
    pattern: str
    reason: str


FORBIDDEN_PATTERNS: tuple[ForbiddenWorldModelPattern, ...] = (
    ForbiddenWorldModelPattern(
        pattern="WorldModel(LTVModel())",
        reason="direct legacy world model wiring bypasses canonical builder",
    ),
    ForbiddenWorldModelPattern(
        pattern="from core.economics.ltv_world_model import WorldModel",
        reason="direct import of legacy WorldModel into boot/runtime paths is forbidden",
    ),
    ForbiddenWorldModelPattern(
        pattern="world_model=WorldModel(",
        reason="direct legacy world model injection is forbidden",
    ),
)

DEFAULT_EXCLUDED_BASENAMES = {
    "world_model_forbidden_paths.py",
    "migrate_world_model_to_canonical.py",
    "test_world_model_forbidden_paths.py",
    "test_migrate_world_model_to_canonical.py",
    "test_check_world_model_integrity_script.py",
    "ltv_world_model.py",
}

# Runtime self-checks inspect canonical source, never dependency, build, report,
# cache, or mutable-state trees. Rust target output can contain hundreds of
# thousands of entries and must not turn boot into an unbounded filesystem walk.
DEFAULT_EXCLUDED_DIRNAMES = {
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
    "dist",
    "htmlcov",
    "node_modules",
    "target",
    "tests",
    "venv",
}

DEFAULT_EXCLUDED_ROOT_DIRNAMES = {
    "_audit",
    "data",
    "reports",
    "runtime_state",
}

_ALLOWED_TEST_BASENAMES = (
    "test_decision_core_world_model_contract.py",
    "test_world_model_contract_runtime.py",
)

_AST_CANDIDATE_TOKENS = (
    b"WorldModel",
    b"ltv_world_model",
)


def _is_name(node: ast.AST, expected: str) -> bool:
    return isinstance(node, ast.Name) and node.id == expected


def _keyword_value_is_worldmodel(call: ast.Call, keyword_name: str) -> bool:
    for kw in call.keywords:
        if kw.arg == keyword_name and _is_name(kw.value, "WorldModel"):
            return True
    return False


def _candidate_source_text(path: Path) -> str | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if not any(token in payload for token in _AST_CANDIDATE_TOKENS):
        return None
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_ast(path: Path, rel: str) -> list[dict]:
    findings: list[dict] = []
    text = _candidate_source_text(path)
    if text is None:
        return findings
    try:
        tree = ast.parse(text, filename=rel)
    except (SyntaxError, ValueError):
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "core.economics.ltv_world_model":
                for alias in node.names:
                    if alias.name == "WorldModel":
                        findings.append(
                            {
                                "path": str(path),
                                "pattern": (
                                    "from core.economics.ltv_world_model "
                                    "import WorldModel"
                                ),
                                "reason": (
                                    "direct import of legacy WorldModel into "
                                    "boot/runtime paths is forbidden"
                                ),
                            }
                        )
        elif isinstance(node, ast.Call):
            if _is_name(node.func, "WorldModel") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Call) and _is_name(first.func, "LTVModel"):
                    findings.append(
                        {
                            "path": str(path),
                            "pattern": "WorldModel(LTVModel())",
                            "reason": (
                                "direct legacy world model wiring bypasses "
                                "canonical builder"
                            ),
                        }
                    )
            if _keyword_value_is_worldmodel(node, "world_model"):
                findings.append(
                    {
                        "path": str(path),
                        "pattern": "world_model=WorldModel(",
                        "reason": "direct legacy world model injection is forbidden",
                    }
                )
    return findings


def _iter_scannable_paths(repo_root: Path, suffixes: tuple[str, ...]) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(
        repo_root,
        topdown=True,
        followlinks=False,
    ):
        base = Path(directory)
        relative_dir = base.relative_to(repo_root)
        at_repo_root = not relative_dir.parts
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in DEFAULT_EXCLUDED_DIRNAMES
            and not (at_repo_root and name in DEFAULT_EXCLUDED_ROOT_DIRNAMES)
        )
        for filename in sorted(filenames):
            path = base / filename
            if path.suffix not in suffixes:
                continue
            if path.name in DEFAULT_EXCLUDED_BASENAMES:
                continue
            yield path

    tests_root = repo_root / "tests"
    for filename in _ALLOWED_TEST_BASENAMES:
        path = tests_root / filename
        if path.is_file() and path.suffix in suffixes:
            yield path


def scan_repo_for_forbidden_world_model_paths(
    *,
    repo_root: str | Path,
    include_suffixes: Iterable[str] = (".py",),
) -> list[dict]:
    root = Path(repo_root)
    findings: list[dict] = []
    suffixes = tuple(include_suffixes)

    for path in _iter_scannable_paths(root, suffixes):
        rel = str(path.relative_to(root)).replace("\\", "/")
        findings.extend(_scan_ast(path, rel))
    return findings
