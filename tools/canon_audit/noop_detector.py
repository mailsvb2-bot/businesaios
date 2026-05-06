from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


def _is_noop_fn(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    body = node.body
    if not body:
        return True
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Return) and stmt.value is None:
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            return True
        if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call) and isinstance(stmt.exc.func, ast.Name) and stmt.exc.func.id == "NotImplementedError":
            return True
    return False


def scan_noop_functions(root: Path, include_paths: Sequence[str] | None = None) -> List[ArchitectureViolation]:
    violations: List[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if _is_noop_fn(node):
                fn_name = node.name  # type: ignore[attr-defined]
                if not fn_name.startswith("test_"):
                    violations.append(ArchitectureViolation("CANON_NOOP_FUNCTION", f"No-op or placeholder function detected: {fn_name}", module_name))
    return violations
