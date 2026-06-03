from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List
from collections.abc import Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


def detect_export_name_collisions(root: Path, include_paths: Sequence[str] | None = None) -> List[ArchitectureViolation]:
    by_name: Dict[str, List[str]] = {}
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                by_name.setdefault(node.name, []).append(module_name)
    violations: List[ArchitectureViolation] = []
    for name, modules in by_name.items():
        if len(set(modules)) > 3:
            violations.append(ArchitectureViolation("CANON_AST_EXPORT_COLLISION", f"Public-like AST export name '{name}' appears in many modules: {sorted(set(modules))[:10]}", name))
    return violations
