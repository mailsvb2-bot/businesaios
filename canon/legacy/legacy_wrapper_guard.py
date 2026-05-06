from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig
from canon.legacy.synonym_entity_registry import is_synonym_of


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
    stem = Path(relpath).stem.lower()
    normalized = relpath.lower()
    basename = Path(relpath).name.lower()
    if basename == "public_api.py":
        return config.is_decision_surface(relpath)
    if basename == "public_api_alias.py":
        return True
    if "compat" in normalized and (config.is_decision_surface(relpath) or normalized.startswith("runtime/")):
        return True
    if normalized.startswith(("core/application/", "core/decision/", "runtime/boot/", "runtime/application/")) and any(
        token in normalized for token in ("alias", "wrapper", "facade")
    ):
        return True
    return is_synonym_of("thin_wrapper", stem) and config.is_decision_surface(relpath)


def _count_non_empty_non_comment_lines(text: str) -> int:
    total = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            total += 1
    return total


def _is_simple_forwarder_return(node: ast.AST) -> bool:
    if isinstance(node, ast.Return):
        return isinstance(node.value, (ast.Call, ast.Name, ast.Attribute, ast.Constant))
    return isinstance(node, ast.Pass)


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

        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        size = _count_non_empty_non_comment_lines(text)
        if size > config.max_thin_wrapper_non_empty_lines:
            findings.append(
                WrapperViolation(
                    relpath=relpath,
                    lineno=1,
                    symbol=Path(relpath).stem,
                    severity=FindingSeverity.MAJOR,
                    reason=f"thin wrapper exceeded logical size budget: {size}>{config.max_thin_wrapper_non_empty_lines}",
                )
            )

        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
                continue
            if isinstance(node, ast.FunctionDef):
                if node.name in config.allowed_thin_wrapper_calls:
                    continue
                if len(node.body) > config.max_thin_wrapper_function_body_statements:
                    findings.append(
                        WrapperViolation(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=node.name,
                            severity=FindingSeverity.CRITICAL,
                            reason="wrapper function contains substantial body and can become a second brain",
                        )
                    )
                    continue
                if not all(_is_simple_forwarder_return(stmt) for stmt in node.body):
                    findings.append(
                        WrapperViolation(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=node.name,
                            severity=FindingSeverity.CRITICAL,
                            reason="wrapper function is not a pure forwarder",
                        )
                    )
            elif isinstance(node, ast.ClassDef):
                findings.append(
                    WrapperViolation(
                        relpath=relpath,
                        lineno=node.lineno,
                        symbol=node.name,
                        severity=FindingSeverity.CRITICAL,
                        reason="wrapper/class compatibility surface is forbidden; wrappers must stay function/module-thin",
                    )
                )
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                name = _call_name(node.value)
                if name not in config.allowed_thin_wrapper_calls:
                    findings.append(
                        WrapperViolation(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=name or "<call>",
                            severity=FindingSeverity.MAJOR,
                            reason="wrapper performs runtime call outside approved alias installer allowlist",
                        )
                    )
            else:
                findings.append(
                    WrapperViolation(
                        relpath=relpath,
                        lineno=getattr(node, "lineno", 1),
                        symbol=type(node).__name__,
                        severity=FindingSeverity.MAJOR,
                        reason="wrapper contains non-thin top-level behavior",
                    )
                )

    return tuple(sorted(findings, key=lambda item: (item.relpath, item.lineno, item.symbol)))


__all__ = [
    "WrapperViolation",
    "scan_legacy_wrappers",
]
