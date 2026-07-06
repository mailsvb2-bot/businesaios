from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from canon.collapse.decision_path_map import FindingSeverity, LegacyCanonConfig
from canon.collapse.synonym_entity_registry import is_synonym_of


@dataclass(frozen=True)
class WrapperViolation:
    relpath: str
    lineno: int
    symbol: str
    severity: FindingSeverity
    reason: str


def _iter_python_files(config: LegacyCanonConfig) -> Iterable[Path]:
    for path in config.repo_root.rglob("*.py"):
        relpath = config.normalize_relpath(path)
        if config.is_included_relpath(relpath):
            yield path


def _is_wrapper_candidate(config: LegacyCanonConfig, relpath: str) -> bool:
    stem, normalized, basename = Path(relpath).stem.lower(), relpath.lower(), Path(relpath).name.lower()
    if basename == "public_api.py":
        return config.is_decision_surface(relpath)
    if basename == "public_api_alias.py":
        return True
    if "compat" in normalized and (config.is_decision_surface(relpath) or normalized.startswith("runtime/")):
        return True
    if normalized.startswith(("core/application/", "core/decision/", "runtime/boot/", "runtime/application/")) and any(token in normalized for token in ("alias", "wrapper", "facade")):
        return True
    return is_synonym_of("thin_wrapper", stem) and config.is_decision_surface(relpath)


def _count_non_empty_non_comment_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("#"))


def _is_simple_forwarder_return(node: ast.AST) -> bool:
    return isinstance(node, ast.Pass) or (isinstance(node, ast.Return) and isinstance(node.value, ast.Call | ast.Name | ast.Attribute | ast.Constant))


def _call_name(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def scan_legacy_wrappers(config: LegacyCanonConfig) -> tuple[WrapperViolation, ...]:
    findings: list[WrapperViolation] = []
    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        if not _is_wrapper_candidate(config, relpath):
            continue
        text, tree = path.read_text(encoding="utf-8"), ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        size = _count_non_empty_non_comment_lines(text)
        if size > config.max_thin_wrapper_non_empty_lines:
            findings.append(WrapperViolation(relpath, 1, Path(relpath).stem, FindingSeverity.MAJOR, f"thin wrapper exceeded logical size budget: {size}>{config.max_thin_wrapper_non_empty_lines}"))
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            if isinstance(node, ast.Import | ast.ImportFrom | ast.Assign | ast.AnnAssign):
                continue
            if isinstance(node, ast.FunctionDef):
                if node.name in config.allowed_thin_wrapper_calls:
                    continue
                if len(node.body) > config.max_thin_wrapper_function_body_statements:
                    findings.append(WrapperViolation(relpath, node.lineno, node.name, FindingSeverity.CRITICAL, "wrapper function contains substantial body and can become a second brain"))
                    continue
                if not all(_is_simple_forwarder_return(stmt) for stmt in node.body):
                    findings.append(WrapperViolation(relpath, node.lineno, node.name, FindingSeverity.CRITICAL, "wrapper function is not a pure forwarder"))
            elif isinstance(node, ast.ClassDef):
                findings.append(WrapperViolation(relpath, node.lineno, node.name, FindingSeverity.CRITICAL, "wrapper/class compatibility surface is forbidden; wrappers must stay function/module-thin"))
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                name = _call_name(node.value)
                if name not in config.allowed_thin_wrapper_calls:
                    findings.append(WrapperViolation(relpath, node.lineno, name or "<call>", FindingSeverity.MAJOR, "wrapper performs runtime call outside approved alias installer allowlist"))
            else:
                findings.append(WrapperViolation(relpath, getattr(node, "lineno", 1), type(node).__name__, FindingSeverity.MAJOR, "wrapper contains non-thin top-level behavior"))
    return tuple(sorted(findings, key=lambda item: (item.relpath, item.lineno, item.symbol)))


__all__ = ["WrapperViolation", "scan_legacy_wrappers"]