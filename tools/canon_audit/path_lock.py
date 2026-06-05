from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import List

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path

FORBIDDEN_NAMES = (
    "execute_direct",
    "run_direct",
    "raw_execute",
    "bypass_verification",
    "skip_verification",
    "bypass_memory",
    "bypass_evidence",
    "manual_decision",
)


def scan_path_lock_bypasses(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.lower() in FORBIDDEN_NAMES:
                violations.append(ArchitectureViolation("CANON_PATH_LOCK_BYPASS", f"Forbidden bypass function detected: {node.name}", module_name))
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id.lower() in FORBIDDEN_NAMES:
                    violations.append(ArchitectureViolation("CANON_PATH_LOCK_BYPASS_CALL", f"Forbidden bypass call detected: {func.id}", module_name))
                elif isinstance(func, ast.Attribute) and func.attr.lower() in FORBIDDEN_NAMES:
                    violations.append(ArchitectureViolation("CANON_PATH_LOCK_BYPASS_CALL", f"Forbidden bypass call detected: {func.attr}", module_name))
    return violations
