from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List
from collections.abc import Iterable, Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


@dataclass(frozen=True)
class FileScanResult:
    module_name: str
    file_path: Path
    text: str
    tree: ast.AST


def iter_project_files(root: Path, include_paths: Sequence[str] | None = None) -> Iterable[FileScanResult]:
    for file_path in collect_python_files(root, include_paths=include_paths):
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file_path))
        yield FileScanResult(module_name_from_path(root, file_path), file_path, text, tree)


def scan_dynamic_export_magic(root: Path, include_paths: Sequence[str] | None = None) -> List[ArchitectureViolation]:
    violations: List[ArchitectureViolation] = []
    for item in iter_project_files(root, include_paths=include_paths):
        if "__getattr__(" in item.text:
            violations.append(ArchitectureViolation("CANON_DYNAMIC_EXPORT_MAGIC", "Package/module-level __getattr__ detected.", item.module_name))
        if "sys.modules" in item.text:
            violations.append(ArchitectureViolation("CANON_DYNAMIC_EXPORT_MAGIC", "sys.modules mutation detected.", item.module_name))
        if "importlib.import_module" in item.text:
            violations.append(ArchitectureViolation("CANON_DYNAMIC_EXPORT_MAGIC", "Dynamic importlib.import_module detected.", item.module_name))
    return violations


def scan_god_modules(root: Path, max_loc: int = 500, max_functions: int = 25, max_classes: int = 10, include_paths: Sequence[str] | None = None) -> List[ArchitectureViolation]:
    violations: List[ArchitectureViolation] = []
    for item in iter_project_files(root, include_paths=include_paths):
        loc = len(item.text.splitlines())
        func_count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(item.tree))
        class_count = sum(isinstance(n, ast.ClassDef) for n in ast.walk(item.tree))
        if loc > max_loc or func_count > max_functions or class_count > max_classes:
            violations.append(ArchitectureViolation("CANON_GOD_MODULE", f"Potential god-module: loc={loc}, functions={func_count}, classes={class_count}", item.module_name))
    return violations
