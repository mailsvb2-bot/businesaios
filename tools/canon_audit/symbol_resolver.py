from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

from tools.canon_audit.import_graph import collect_python_files, module_name_from_path
from tools.canon_audit.symbol_table import build_symbol_tables


@dataclass(frozen=True)
class ResolvedRef:
    module_name: str
    symbol_name: Optional[str]

    @property
    def pretty(self) -> str:
        return f"{self.module_name}:{self.symbol_name}" if self.symbol_name else self.module_name


@dataclass
class ModuleBindings:
    module_name: str
    aliases: Dict[str, ResolvedRef] = field(default_factory=dict)


def _resolve_relative_module(module_name: str, is_init: bool, level: int, target_module: Optional[str]) -> str:
    parts = module_name.split(".")
    if not is_init:
        parts = parts[:-1]
    base = parts[: max(0, len(parts) - level + 1)]
    if target_module:
        return ".".join(base + target_module.split("."))
    return ".".join(base)


def build_bindings_index(root: Path, include_paths: Sequence[str] | None = None) -> Dict[str, ModuleBindings]:
    tables = build_symbol_tables(root, include_paths=include_paths)
    index: Dict[str, ModuleBindings] = {}

    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file_path))
        bindings = ModuleBindings(module_name=module_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    bindings.aliases[local] = ResolvedRef(alias.name, None)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    target_module = _resolve_relative_module(module_name, file_path.name == "__init__.py", node.level, node.module)
                else:
                    if not node.module:
                        continue
                    target_module = node.module
                for alias in node.names:
                    local = alias.asname or alias.name
                    bindings.aliases[local] = ResolvedRef(target_module, alias.name)

        table = tables.get(module_name)
        if table:
            for name in table.exports_by_name:
                bindings.aliases.setdefault(name, ResolvedRef(module_name, name))
        index[module_name] = bindings
    return index


def resolve_local_name(module_name: str, local_name: str, bindings_index: Dict[str, ModuleBindings]) -> Optional[ResolvedRef]:
    module_bindings = bindings_index.get(module_name)
    if module_bindings is None:
        return None
    return module_bindings.aliases.get(local_name)
