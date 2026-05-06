from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from tools.canon_audit.import_graph import collect_python_files, module_name_from_path
from tools.canon_audit.symbol_resolver import ResolvedRef, build_bindings_index, resolve_local_name


@dataclass(frozen=True)
class CallEdge:
    caller_fqname: str
    callee_ref: str
    file_path: Path
    lineno: int


@dataclass
class _Frame:
    qualname: str
    local_bindings: Dict[str, ResolvedRef] = field(default_factory=dict)


class _Collector(ast.NodeVisitor):
    def __init__(self, module_name: str, file_path: Path, bindings_index: Dict[str, object]) -> None:
        self.module_name = module_name
        self.file_path = file_path
        self.bindings_index = bindings_index
        self.scope: List[str] = []
        self.frames: List[_Frame] = []
        self.edges: List[CallEdge] = []

    def _current_fqname(self) -> Optional[str]:
        if not self.scope:
            return None
        return f"{self.module_name}:{'.'.join(self.scope)}"

    def _frame(self) -> Optional[_Frame]:
        return self.frames[-1] if self.frames else None

    def _resolve_expr(self, node: ast.expr) -> Optional[ResolvedRef]:
        frame = self._frame()
        if isinstance(node, ast.Name):
            if frame and node.id in frame.local_bindings:
                return frame.local_bindings[node.id]
            return resolve_local_name(self.module_name, node.id, self.bindings_index)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                if frame and node.attr in frame.local_bindings:
                    return frame.local_bindings[node.attr]
            base = self._resolve_expr(node.value)
            if base is None:
                return None
            return ResolvedRef(base.module_name, node.attr)
        return None

    def _bind_target(self, target: ast.expr, resolved: ResolvedRef) -> None:
        frame = self._frame()
        if frame is None:
            return
        if isinstance(target, ast.Name):
            frame.local_bindings[target.id] = resolved
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
            frame.local_bindings[target.attr] = resolved

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            resolved = self._resolve_expr(node.value.func)
            if resolved is not None:
                for target in node.targets:
                    self._bind_target(target, resolved)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.value, ast.Call):
            resolved = self._resolve_expr(node.value.func)
            if resolved is not None:
                self._bind_target(node.target, resolved)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.frames.append(_Frame(".".join(self.scope)))
        self.generic_visit(node)
        self.frames.pop()
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.frames.append(_Frame(".".join(self.scope)))
        self.generic_visit(node)
        self.frames.pop()
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        caller = self._current_fqname()
        if caller:
            resolved = self._resolve_expr(node.func)
            if resolved is not None:
                self.edges.append(CallEdge(caller, resolved.pretty, self.file_path, node.lineno))
        self.generic_visit(node)


def build_call_graph(root: Path, include_paths: Sequence[str] | None = None) -> List[CallEdge]:
    bindings_index = build_bindings_index(root, include_paths=include_paths)
    edges: List[CallEdge] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(file_path))
        collector = _Collector(module_name, file_path, bindings_index)
        collector.visit(tree)
        edges.extend(collector.edges)
    return edges
