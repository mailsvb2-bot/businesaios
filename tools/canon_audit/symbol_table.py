from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


@dataclass(frozen=True)
class ExportedSymbol:
    module_name: str
    symbol_name: str
    qualname: str
    lineno: int

    @property
    def fqname(self) -> str:
        return f"{self.module_name}:{self.qualname}"


@dataclass
class ModuleSymbolTable:
    module_name: str
    exports_by_name: Dict[str, List[ExportedSymbol]] = field(default_factory=dict)


class _Collector(ast.NodeVisitor):
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.scope: List[str] = []
        self.exports: List[ExportedSymbol] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join(self.scope + [node.name])
        self.exports.append(ExportedSymbol(self.module_name, node.name, qualname, node.lineno))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = ".".join(self.scope + [node.name])
        self.exports.append(ExportedSymbol(self.module_name, node.name, qualname, node.lineno))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        qualname = ".".join(self.scope + [node.name])
        self.exports.append(ExportedSymbol(self.module_name, node.name, qualname, node.lineno))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def build_symbol_tables(root: Path, include_paths: Sequence[str] | None = None) -> Dict[str, ModuleSymbolTable]:
    result: Dict[str, ModuleSymbolTable] = {}
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file_path))
        collector = _Collector(module_name)
        collector.visit(tree)
        table = ModuleSymbolTable(module_name=module_name)
        for export in collector.exports:
            table.exports_by_name.setdefault(export.symbol_name, []).append(export)
        result[module_name] = table
    return result
