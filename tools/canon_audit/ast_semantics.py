from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import List

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path

SEMANTIC_ALLOWED_PREFIXES = (
    "application.policy",
    "application.decision",
    "application.world_state",
    "application.capability",
    "application.governance",
)


def _is_allowed(module_name: str) -> bool:
    return any(module_name == p or module_name.startswith(p + ".") for p in SEMANTIC_ALLOWED_PREFIXES)


def _looks_like_business_name(name: str) -> bool:
    lowered = name.lower()
    return any(m in lowered for m in ("score", "penalty", "threshold", "confidence", "risk", "bonus", "weight", "window", "limit", "budget"))


def scan_hidden_semantic_numeric_heuristics(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        if _is_allowed(module_name):
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if names and any(_looks_like_business_name(n) for n in names):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                        violations.append(ArchitectureViolation("CANON_HIDDEN_NUMERIC_HEURISTIC", f"Suspicious semantic numeric heuristic outside semantic owner: {names[0]}={node.value.value!r} at line {node.lineno}", module_name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if _looks_like_business_name(node.target.id):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                        violations.append(ArchitectureViolation("CANON_HIDDEN_NUMERIC_HEURISTIC", f"Suspicious semantic numeric heuristic outside semantic owner: {node.target.id}={node.value.value!r} at line {node.lineno}", module_name))
    return violations
