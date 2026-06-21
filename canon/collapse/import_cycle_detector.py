from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from canon.surface_ceiling import iter_production_python_files


@dataclass(frozen=True)
class ImportCycle:
    modules: tuple[str, ...]
    sample_edges: tuple[str, ...]


@dataclass(frozen=True)
class ImportCycleReport:
    production_python_files: int
    modules: int
    edges: int
    parse_errors: tuple[tuple[str, str], ...]
    p0_cycles: tuple[ImportCycle, ...]


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _current_package(path: Path, module: str) -> str:
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _resolve_relative(current_pkg: str, level: int, mod: str | None) -> str:
    if level <= 0:
        return mod or ""
    parts = current_pkg.split(".") if current_pkg else []
    base = parts[: max(0, len(parts) - level + 1)]
    if mod:
        base.extend(mod.split("."))
    return ".".join(part for part in base if part)


def _existing_module_prefix(name: str, modules: set[str]) -> str | None:
    if not name:
        return None
    parts = name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in modules:
            return candidate
    return None


def _top_level_import_candidates(path: Path, source: str, node: ast.stmt) -> tuple[str, ...]:
    package = _current_package(path, source)

    if isinstance(node, ast.If):
        test = node.test
        if (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        ) or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        ):
            return ()

    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)

    if isinstance(node, ast.ImportFrom):
        base = _resolve_relative(package, node.level, node.module)
        items = []
        if base:
            items.append(base)
            for alias in node.names:
                if alias.name != "*":
                    items.append(base + "." + alias.name)
        return tuple(items)

    return ()


def _strongly_connected_components(graph: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def connect(node: str) -> None:
        indices[node] = len(indices)
        lowlink[node] = indices[node]
        stack.append(node)
        on_stack.add(node)

        for target in graph.get(node, ()):
            if target not in indices:
                connect(target)
                lowlink[node] = min(lowlink[node], lowlink[target])
            elif target in on_stack:
                lowlink[node] = min(lowlink[node], indices[target])

        if lowlink[node] == indices[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            components.append(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indices:
            connect(node)

    return tuple(
        component
        for component in components
        if len(component) > 1 or component[0] in graph.get(component[0], set())
    )


def build_p0_import_cycle_report(repo_root: Path) -> ImportCycleReport:
    root = repo_root.resolve()
    paths = tuple(sorted(path for path in iter_production_python_files(root) if path.exists()))
    module_by_path = {path: _module_name(root, path) for path in paths}
    modules = set(module_by_path.values())

    graph: dict[str, set[str]] = {module: set() for module in modules}
    reasons: dict[tuple[str, str], list[str]] = defaultdict(list)
    parse_errors: list[tuple[str, str]] = []

    for path, source in module_by_path.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as exc:
            parse_errors.append((path.relative_to(root).as_posix(), str(exc)))
            continue

        for node in tree.body:
            for raw in _top_level_import_candidates(path, source, node):
                target = _existing_module_prefix(raw, modules)
                if not target or target == source:
                    continue
                graph[source].add(target)
                reasons[(source, target)].append(
                    f"{source} -> {target} @ {path.relative_to(root).as_posix()}:{getattr(node, 'lineno', 0)} raw={raw}"
                )

    components = _strongly_connected_components(graph)
    cycles = []
    for component in sorted(components, key=lambda item: (-len(item), item[0])):
        edges = []
        for source in component:
            for target in component:
                edges.extend(reasons.get((source, target), [])[:4])
                if len(edges) >= 20:
                    break
            if len(edges) >= 20:
                break
        cycles.append(ImportCycle(modules=component, sample_edges=tuple(edges[:20])))

    return ImportCycleReport(
        production_python_files=len(paths),
        modules=len(modules),
        edges=sum(len(value) for value in graph.values()),
        parse_errors=tuple(parse_errors),
        p0_cycles=tuple(cycles),
    )


__all__ = [
    "ImportCycle",
    "ImportCycleReport",
    "build_p0_import_cycle_report",
]
