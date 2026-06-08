from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from canon.collapse.decision_path_map import FindingSeverity, LegacyCanonConfig


@dataclass(frozen=True)
class GodModuleFinding:
    relpath: str
    severity: FindingSeverity
    lines: int
    functions: int
    classes: int
    imports: int
    reasons: tuple[str, ...]


def _iter_python_files(config: LegacyCanonConfig) -> Iterable[Path]:
    for path in config.repo_root.rglob("*.py"):
        relpath = config.normalize_relpath(path)
        if config.is_included_relpath(relpath):
            yield path


def _non_empty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _class_complexity(node: ast.ClassDef) -> int:
    methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return 0 if not methods else sum(len(item.body) for item in methods)


def _textual_count(text: str, prefixes: tuple[str, ...]) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith(prefixes))


def _needs_ast_complexity_scan(*, text: str, lines: int, config: LegacyCanonConfig, decision_surface: bool) -> bool:
    _ = decision_surface
    return lines > config.god_module_lines_major or _textual_count(text, ("def ", "async def ")) > config.god_module_functions_major or _textual_count(text, ("class ",)) > config.god_module_classes_major or _textual_count(text, ("import ", "from ")) > config.god_module_imports_major


def scan_god_modules(config: LegacyCanonConfig) -> tuple[GodModuleFinding, ...]:
    findings: list[GodModuleFinding] = []
    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        if config.is_god_module_allowlisted(relpath):
            continue
        text = path.read_text(encoding="utf-8")
        lines, decision_surface = _non_empty_line_count(text), config.is_decision_surface(relpath)
        if _needs_ast_complexity_scan(text=text, lines=lines, config=config, decision_surface=decision_surface):
            tree = ast.parse(text, filename=str(path))
            functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
            classes = sum(_class_complexity(node) >= 3 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            imports = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
        else:
            functions, classes, imports = _textual_count(text, ("def ", "async def ")), _textual_count(text, ("class ",)), _textual_count(text, ("import ", "from "))
        critical, major = [], []
        for value, critical_limit, major_limit, label in ((lines, config.god_module_lines_critical, config.god_module_lines_major, "lines"), (functions, config.god_module_functions_critical, config.god_module_functions_major, "functions"), (classes, config.god_module_classes_critical, config.god_module_classes_major, "classes"), (imports, config.god_module_imports_critical, config.god_module_imports_major, "imports")):
            if value > critical_limit:
                critical.append(f"{label}={value}>{critical_limit}")
            elif value > major_limit:
                major.append(f"{label}={value}>{major_limit}")
        if critical:
            findings.append(GodModuleFinding(relpath, FindingSeverity.CRITICAL, lines, functions, classes, imports, tuple(critical)))
        elif major and decision_surface:
            findings.append(GodModuleFinding(relpath, FindingSeverity.MAJOR, lines, functions, classes, imports, tuple(major)))
    return tuple(sorted(findings, key=lambda item: (item.severity.value, item.relpath)))


__all__ = ["GodModuleFinding", "scan_god_modules"]
