from __future__ import annotations

import ast
from pathlib import Path
from typing import List
from collections.abc import Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path

ALLOWED_PREFIXES = (
    "application.policy",
    "application.decision",
    "application.governance",
    "application.capability",
)


def _contains_formula(node: ast.AST) -> bool:
    if isinstance(node, ast.BinOp):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"min", "max", "round"}:
        return True
    return False


def scan_formula_semantics_outside_policy(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        if any(module_name == p or module_name.startswith(p + ".") for p in ALLOWED_PREFIXES):
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not names:
                    continue
                lowered = " ".join(names).lower()
                if any(m in lowered for m in ("score", "penalty", "confidence", "risk", "bonus", "weight")):
                    if _contains_formula(node.value):
                        violations.append(ArchitectureViolation("CANON_FORMULA_OUTSIDE_POLICY", f"Formula-like semantic assignment outside policy owner at line {node.lineno}: {names}", module_name))
    return violations
