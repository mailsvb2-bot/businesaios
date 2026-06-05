from __future__ import annotations

import ast
from pathlib import Path
from typing import List
from collections.abc import Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


def scan_package_root_surfaces(
    root: Path,
    export_threshold: int = 20,
    import_threshold: int = 25,
    include_paths: Sequence[str] | None = None,
) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        if file_path.name != "__init__.py":
            continue
        module_name = module_name_from_path(root, file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        import_count = 0
        all_size = 0
        has_getattr = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_count += 1
            elif isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
                has_getattr = True
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                        all_size = max(all_size, len(node.value.elts))
        if import_count > import_threshold or all_size > export_threshold or has_getattr:
            violations.append(
                ArchitectureViolation(
                    "CANON_GOD_PACKAGE_SURFACE",
                    f"Package root too heavy: imports={import_count}, __all__ size={all_size}, __getattr__={has_getattr}",
                    module_name,
                )
            )
    return violations
