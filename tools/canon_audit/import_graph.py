from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections.abc import Iterable, Sequence

PROJECT_ROOT_PREFIXES = (
    "application",
    "runtime",
    "observability",
    "execution",
    "interfaces",
    "connectors",
    "governance",
    "security",
    "tenancy",
    "storage",
    "config",
    "canon",
    "tools",
    "scripts",
)


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str


def module_name_from_path(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _matches_include_paths(file_path: Path, root: Path, include_paths: Sequence[str] | None) -> bool:
    if not include_paths:
        return True
    rel = file_path.relative_to(root).as_posix()
    return any(rel == prefix or rel.startswith(prefix.rstrip('/') + '/') for prefix in include_paths)


def collect_python_files(root: Path, include_paths: Sequence[str] | None = None) -> List[Path]:
    ignored = {".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
    return sorted(
        p
        for p in root.rglob("*.py")
        if not any(part in ignored for part in p.parts) and _matches_include_paths(p, root, include_paths)
    )


def parse_imports_for_file(root: Path, file_path: Path) -> List[ImportEdge]:
    source_module = module_name_from_path(root, file_path)
    text = file_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(file_path))
    edges: List[ImportEdge] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(ImportEdge(source=source_module, target=alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = source_module.split(".")
                if file_path.name != "__init__.py":
                    parts = parts[:-1]
                base = parts[: max(0, len(parts) - node.level + 1)]
                target = ".".join(base + (node.module.split(".") if node.module else []))
            else:
                if not node.module:
                    continue
                target = node.module
            if target:
                edges.append(ImportEdge(source=source_module, target=target))
    return edges


def build_import_graph(root: Path, include_paths: Sequence[str] | None = None) -> List[ImportEdge]:
    edges: List[ImportEdge] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        edges.extend(parse_imports_for_file(root, file_path))
    return edges


def _is_internal(name: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in PROJECT_ROOT_PREFIXES)


def internal_import_edges(edges: Iterable[ImportEdge]) -> List[ImportEdge]:
    return [e for e in edges if _is_internal(e.source) and _is_internal(e.target)]


def detect_cycles(edges: Iterable[ImportEdge]) -> List[Tuple[str, ...]]:
    adjacency: Dict[str, Set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)

    visited: Set[str] = set()
    active: Set[str] = set()
    stack: List[str] = []
    cycles: List[Tuple[str, ...]] = []

    def dfs(node: str) -> None:
        visited.add(node)
        active.add(node)
        stack.append(node)
        for nxt in adjacency.get(node, set()):
            if nxt not in visited:
                dfs(nxt)
            elif nxt in active:
                idx = stack.index(nxt)
                cycles.append(tuple(stack[idx:] + [nxt]))
        active.remove(node)
        stack.pop()

    for node in adjacency:
        if node not in visited:
            dfs(node)

    result: List[Tuple[str, ...]] = []
    seen = set()
    for cycle in cycles:
        if cycle not in seen:
            seen.add(cycle)
            result.append(cycle)
    return result
