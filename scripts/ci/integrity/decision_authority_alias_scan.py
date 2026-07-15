from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from scripts.ci.integrity import auditor

CANON_SECOND_BRAIN_ALIAS_SCAN = True

_AUTHORITY_TOKENS = (
    "decisioncore",
    "decisionengine",
    "plannerengine",
    "secondbrain",
    "shadowbrain",
    "alternatebrain",
    "localbrain",
)
_AUTHORITY_METHODS = frozenset({"decide", "issue", "optimize"})
_INTERFACE_SUFFIXES = ("Port", "Protocol", "Contract", "Spec", "Ref")
_SUSPICIOUS_AUTHORITY_PREFIXES = (
    "alternate",
    "autopilot",
    "backup",
    "experimental",
    "fake",
    "fallback",
    "legacy",
    "local",
    "private",
    "second",
    "secondary",
    "shadow",
)
_RUNTIME_DECISION_CORE_TRIPWIRE_PATH = "boot/runtime_service_contracts.py"
_RUNTIME_DECISION_CORE_TRIPWIRE_NAME = "RuntimeDecisionCore"
_RUNTIME_DECISION_CORE_TRIPWIRE_MARKER = "CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE"


def _normalized(name: str) -> str:
    return "".join(ch for ch in str(name or "").casefold() if ch.isalnum())


def _normalized_type_stem(name: str) -> str:
    return re.sub(r"v?\d+$", "", _normalized(name))


def _looks_like_decision_authority_alias(name: str, executable_names: set[str]) -> bool:
    text = str(name or "")
    if text in executable_names:
        return True

    # Snake-case names such as `decision_core` are dependency/instance bindings,
    # not exported authority type surfaces. Assignment/import checks target
    # exported aliases such as RuntimeDecisionCore or DecisionEngine.
    if not any(ch.isupper() for ch in text):
        return False

    normalized = _normalized(text)
    return any(token in normalized for token in _AUTHORITY_TOKENS)


def _is_authority_type_definition_name(name: str, executable_names: set[str]) -> bool:
    if str(name) in executable_names:
        return True
    stem = _normalized_type_stem(name)
    return any(stem.endswith(token) for token in _AUTHORITY_TOKENS)


def _is_authority_function_definition_name(name: str, executable_names: set[str]) -> bool:
    text = str(name or "")
    if text in executable_names:
        return True

    stem = _normalized_type_stem(text)
    executable_stems = {_normalized_type_stem(item) for item in executable_names}
    if stem in executable_stems or stem in _AUTHORITY_TOKENS:
        return True

    # CamelCase authority-shaped callables are exported executable surfaces.
    if any(ch.isupper() for ch in text):
        return any(stem.endswith(token) for token in _AUTHORITY_TOKENS)

    # Snake-case lifecycle helpers such as validate_*, build_* and register_*
    # are not authorities by name alone. Explicit shadow/fallback/alternate
    # authority definitions remain forbidden.
    return any(
        stem.startswith(prefix) and stem.endswith(token)
        for prefix in _SUSPICIOUS_AUTHORITY_PREFIXES
        for token in _AUTHORITY_TOKENS
    )


def _class_method_names(node: ast.ClassDef) -> set[str]:
    return {
        child.name
        for child in node.body
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _method_is_abstract_contract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    decorator_names = {_decorator_name(item) for item in node.decorator_list}
    if any(name.endswith("abstractmethod") for name in decorator_names):
        return True

    statements = list(node.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(statements[0].value, ast.Constant) and isinstance(statements[0].value.value, str):
        statements = statements[1:]
    if len(statements) != 1:
        return False

    statement = statements[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis:
        return True
    if isinstance(statement, ast.Raise):
        exc = statement.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
            return True
        if isinstance(exc, ast.Attribute) and exc.attr == "NotImplementedError":
            return True
    return False


def _is_pure_authority_interface(node: ast.ClassDef) -> bool:
    if not node.name.endswith(_INTERFACE_SUFFIXES):
        return False
    authority_methods = [
        child
        for child in node.body
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name in _AUTHORITY_METHODS
    ]
    return bool(authority_methods) and all(_method_is_abstract_contract(method) for method in authority_methods)


def _class_has_true_marker(node: ast.ClassDef, marker: str) -> bool:
    for child in node.body:
        if not isinstance(child, ast.Assign):
            continue
        if not isinstance(child.value, ast.Constant) or child.value.value is not True:
            continue
        if any(isinstance(target, ast.Name) and target.id == marker for target in child.targets):
            return True
    return False


def _init_raises_runtime_error(node: ast.ClassDef) -> bool:
    init = next(
        (
            child
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name == "__init__"
        ),
        None,
    )
    if init is None:
        return False
    for child in ast.walk(init):
        if not isinstance(child, ast.Raise) or not isinstance(child.exc, ast.Call):
            continue
        func = child.exc.func
        if isinstance(func, ast.Name) and func.id == "RuntimeError":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "RuntimeError":
            return True
    return False


def _is_fail_closed_runtime_decision_core_tripwire(*, relative: str, node: ast.ClassDef) -> bool:
    if relative != _RUNTIME_DECISION_CORE_TRIPWIRE_PATH or node.name != _RUNTIME_DECISION_CORE_TRIPWIRE_NAME:
        return False
    methods = _class_method_names(node)
    return (
        _class_has_true_marker(node, _RUNTIME_DECISION_CORE_TRIPWIRE_MARKER)
        and _init_raises_runtime_error(node)
        and not (methods & _AUTHORITY_METHODS)
    )


def _assigned_names(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> tuple[ast.Name, ...]:
    targets: list[ast.AST]
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        targets = [node.target]

    names: list[ast.Name] = []
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.append(child)
    return tuple(names)


def _value_can_expose_executable(value: ast.AST) -> bool:
    if isinstance(value, ast.Constant):
        return False
    if isinstance(value, ast.Name | ast.Attribute | ast.Call | ast.Lambda | ast.Subscript):
        return True
    if isinstance(value, ast.IfExp):
        return _value_can_expose_executable(value.body) or _value_can_expose_executable(value.orelse)
    if isinstance(value, ast.List | ast.Set | ast.Tuple):
        return any(_value_can_expose_executable(item) for item in value.elts)
    if isinstance(value, ast.Dict):
        return any(
            item is not None and _value_can_expose_executable(item)
            for item in value.values
        )
    return False


def _definition_finding(*, path: Path, node: ast.AST, name: str, kind: str) -> auditor.Finding:
    return auditor.finding(
        "P0_DECISION_AUTHORITY_DEFINITION",
        "P0",
        "Competing executable decision authority definition",
        path,
        getattr(node, "lineno", 1),
        f"{kind} `{name}` exposes a competing decision-authority surface outside canonical DecisionCore.",
        "Delete the authority. Keep decision issuance exclusively in core.ai.decision_core.DecisionCore.",
    )


def _alias_findings_for_path(path: Path, spec: dict[str, Any]) -> list[auditor.Finding]:
    relative = auditor.rel(path)
    if relative.startswith("tests/") or relative in auditor.ALLOWED_NEGATIVE_BRAIN_GUARD_PATHS:
        return []
    if relative == auditor.CANONICAL_DECISION_CORE_PATH:
        return []

    tree = auditor.parse_file(path)
    if tree is None:
        return []

    executable_names = auditor._executable_decision_authority_names(spec)
    findings: list[auditor.Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if _is_fail_closed_runtime_decision_core_tripwire(relative=relative, node=node):
                continue
            if _is_pure_authority_interface(node):
                continue
            authority_methods = _class_method_names(node) & _AUTHORITY_METHODS
            if _is_authority_type_definition_name(node.name, executable_names) or (
                authority_methods and _looks_like_decision_authority_alias(node.name, executable_names)
            ):
                findings.append(_definition_finding(path=path, node=node, name=node.name, kind="Class"))
            continue

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_authority_function_definition_name(node.name, executable_names):
                findings.append(_definition_finding(path=path, node=node, name=node.name, kind="Function"))
            continue

        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is None:
                    continue
                if alias.name.isupper() and alias.asname.isupper():
                    continue
                if not _looks_like_decision_authority_alias(alias.asname, executable_names):
                    continue
                findings.append(
                    auditor.finding(
                        "P0_DECISION_AUTHORITY_ALIAS",
                        "P0",
                        "Executable decision authority import alias",
                        path,
                        getattr(node, "lineno", 1),
                        f"Import alias `{alias.name} as {alias.asname}` creates a competing decision-authority surface.",
                        "Import the canonical DecisionCore under its canonical name and keep runtime/services as non-authoritative callers.",
                    )
                )
            continue

        if not isinstance(node, ast.Assign | ast.AnnAssign | ast.NamedExpr):
            continue

        value = getattr(node, "value", None)
        if value is None or not _value_can_expose_executable(value):
            continue
        for target in _assigned_names(node):
            if not _looks_like_decision_authority_alias(target.id, executable_names):
                continue
            findings.append(
                auditor.finding(
                    "P0_DECISION_AUTHORITY_ALIAS",
                    "P0",
                    "Executable decision authority assignment alias",
                    path,
                    getattr(node, "lineno", 1),
                    f"Assignment to `{target.id}` can expose a second executable decision authority.",
                    "Delete the alias. Route all decision issuance through core.ai.decision_core.DecisionCore.",
                )
            )

    return findings


def check_decision_authority_aliases(files: list[Path], spec: dict[str, Any]) -> list[auditor.Finding]:
    findings: list[auditor.Finding] = []
    for path in files:
        findings.extend(_alias_findings_for_path(path, spec))
    return findings


__all__ = ["CANON_SECOND_BRAIN_ALIAS_SCAN", "check_decision_authority_aliases"]
