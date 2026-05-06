from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


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


def _is_name(node: ast.AST, expected: str) -> bool:
    return isinstance(node, ast.Name) and node.id == expected


def _keyword_value_is_worldmodel(call: ast.Call, keyword_name: str) -> bool:
    for kw in call.keywords:
        if kw.arg == keyword_name and _is_name(kw.value, "WorldModel"):
            return True
    return False


def _scan_ast(path: Path, rel: str) -> List[dict]:
    findings: List[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rel)
    except Exception:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "core.economics.ltv_world_model":
                for alias in node.names:
                    if alias.name == "WorldModel":
                        findings.append(
                            {
                                "path": str(path),
                                "pattern": "from core.economics.ltv_world_model import WorldModel",
                                "reason": "direct import of legacy WorldModel into boot/runtime paths is forbidden",
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
                            "reason": "direct legacy world model wiring bypasses canonical builder",
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


def scan_repo_for_forbidden_world_model_paths(
    *,
    repo_root: str | Path,
    include_suffixes: Iterable[str] = (".py",),
) -> List[dict]:
    repo_root = Path(repo_root)
    findings: List[dict] = []
    suffixes = tuple(include_suffixes)

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in suffixes:
            continue
        if path.name in DEFAULT_EXCLUDED_BASENAMES:
            continue
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        rel_parts = Path(rel).parts
        if "tests" in rel_parts and path.name not in {"test_world_model_contract_runtime.py", "test_decision_core_world_model_contract.py"}:
            continue

        findings.extend(_scan_ast(path, rel))
    return findings
