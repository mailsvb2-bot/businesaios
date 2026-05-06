from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig


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
    if not methods:
        return 0
    return sum(len(item.body) for item in methods)


def _textual_count(text: str, prefixes: tuple[str, ...]) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith(prefixes))


def _needs_ast_complexity_scan(*, text: str, lines: int, config: LegacyCanonConfig, decision_surface: bool) -> bool:
    """Return True only when a file is close enough to god-module thresholds.

    The god-module lock used to parse every included Python file into an AST. On
    the real repository this made the Canon suite look like it was hanging even
    when most files were tiny wrappers. This bounded prefilter is conservative:
    it skips AST parsing only when textual counts are already below every major
    threshold that can matter for a finding. Critical line-count findings are
    still detected without AST parsing.
    """

    if lines > config.god_module_lines_major:
        return True
    textual_functions = _textual_count(text, ("def ", "async def "))
    if textual_functions > config.god_module_functions_major:
        return True
    textual_classes = _textual_count(text, ("class ",))
    if textual_classes > config.god_module_classes_major:
        return True
    textual_imports = _textual_count(text, ("import ", "from "))
    if textual_imports > config.god_module_imports_major:
        return True
    return False


def scan_god_modules(config: LegacyCanonConfig) -> tuple[GodModuleFinding, ...]:
    findings: list[GodModuleFinding] = []

    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        if config.is_god_module_allowlisted(relpath):
            continue

        text = path.read_text(encoding="utf-8")
        lines = _non_empty_line_count(text)
        decision_surface = config.is_decision_surface(relpath)

        if _needs_ast_complexity_scan(text=text, lines=lines, config=config, decision_surface=decision_surface):
            tree = ast.parse(text, filename=str(path))
            functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
            classes = sum(_class_complexity(node) >= 3 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            imports = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
        else:
            functions = _textual_count(text, ("def ", "async def "))
            classes = _textual_count(text, ("class ",))
            imports = _textual_count(text, ("import ", "from "))

        critical_reasons: list[str] = []
        major_reasons: list[str] = []

        if lines > config.god_module_lines_critical:
            critical_reasons.append(f"lines={lines}>{config.god_module_lines_critical}")
        elif lines > config.god_module_lines_major:
            major_reasons.append(f"lines={lines}>{config.god_module_lines_major}")

        if functions > config.god_module_functions_critical:
            critical_reasons.append(f"functions={functions}>{config.god_module_functions_critical}")
        elif functions > config.god_module_functions_major:
            major_reasons.append(f"functions={functions}>{config.god_module_functions_major}")

        if classes > config.god_module_classes_critical:
            critical_reasons.append(f"classes={classes}>{config.god_module_classes_critical}")
        elif classes > config.god_module_classes_major:
            major_reasons.append(f"classes={classes}>{config.god_module_classes_major}")

        if imports > config.god_module_imports_critical:
            critical_reasons.append(f"imports={imports}>{config.god_module_imports_critical}")
        elif imports > config.god_module_imports_major:
            major_reasons.append(f"imports={imports}>{config.god_module_imports_major}")

        if critical_reasons:
            findings.append(
                GodModuleFinding(
                    relpath=relpath,
                    severity=FindingSeverity.CRITICAL,
                    lines=lines,
                    functions=functions,
                    classes=classes,
                    imports=imports,
                    reasons=tuple(critical_reasons),
                )
            )
        elif major_reasons and decision_surface:
            findings.append(
                GodModuleFinding(
                    relpath=relpath,
                    severity=FindingSeverity.MAJOR,
                    lines=lines,
                    functions=functions,
                    classes=classes,
                    imports=imports,
                    reasons=tuple(major_reasons),
                )
            )

    return tuple(sorted(findings, key=lambda item: (item.severity.value, item.relpath)))


__all__ = [
    "GodModuleFinding",
    "scan_god_modules",
]
