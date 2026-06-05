from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import List

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path

MARKERS = ("container", "service_locator", "registry", "provider_map", "bindings", "injector", "resolver", "wiring")


def scan_di_container_antipatterns(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        text = file_path.read_text(encoding="utf-8")
        lowered = text.lower()
        hits = [m for m in MARKERS if m in lowered]
        if not hits:
            continue
        tree = ast.parse(text, filename=str(file_path))
        dynamic_map = any(isinstance(n, ast.Dict) and len(n.keys) >= 3 for n in ast.walk(tree))
        named_container = any(isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and any(m in n.name.lower() for m in MARKERS) for n in ast.walk(tree))
        if dynamic_map or named_container:
            violations.append(ArchitectureViolation("CANON_DI_CONTAINER", f"DI/container/service-locator anti-pattern markers detected: {sorted(set(hits))}, dynamic_map={dynamic_map}, named_container_scope={named_container}", module_name))
    return violations
