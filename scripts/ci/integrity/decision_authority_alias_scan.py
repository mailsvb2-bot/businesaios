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
_NON_EXECUTABLE_DATA_SUFFIXES = ("_DEPS", "_IMPORT_PATH", "_SYNONYMS")
_CANONICAL_SINGLETON_PATH = "core/ai/__init__.py"
_CANONICAL_SINGLETON_NAME = "_DECISION_CORE_SINGLETON"
_CANONICAL_SINGLETON_SETTER = "set_decision_core_singleton"
_NON_RUNTIME_REGRESSION_FIXTURE_PATH = "formal/regression_gate/project_snapshot_bundle.py"
_NON_RUNTIME_REGRESSION_FIXTURE_MARKER = "CANON_NON_RUNTIME_REGRESSION_FIXTURE"
_NON_RUNTIME_REGRESSION_FIXTURE_NAMES = frozenset(
    {"_RejectingDecisionCore", "_SelectingDecisionCore"}
)


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


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef):
            return parent
        parent = parents.get(parent)
    return None


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


def _is_plain_frozen_data_class(node: ast.ClassDef) -> bool:
    if node.bases or node.keywords or len(node.decorator_list) != 1:
        return False
    frozen_dataclass = False
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not _decorator_name(decorator.func).endswith("dataclass"):
            continue
        frozen_dataclass = any(
            keyword.arg == "frozen"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in decorator.keywords
        )
    if not frozen_dataclass:
        return False

    for child in node.body:
        if isinstance(child, ast.AnnAssign) and child.value is None:
            continue
        if isinstance(child, ast.Pass):
            continue
        if (
            isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Constant)
            and isinstance(child.value.value, str)
        ):
            continue
        return False
    return True


def _plain_frozen_data_type_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in getattr(tree, "body", ())
        if isinstance(node, ast.ClassDef) and _is_plain_frozen_data_class(node)
    }


def _has_non_executable_data_suffix(name: str) -> bool:
    return str(name or "").upper().endswith(_NON_EXECUTABLE_DATA_SUFFIXES)


def _terminal_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_proven_non_executable_data_value(
    value: ast.AST,
    *,
    plain_data_types: set[str],
) -> bool:
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Name | ast.Attribute):
        return _has_non_executable_data_suffix(_terminal_name(value))
    if isinstance(value, ast.List | ast.Set | ast.Tuple):
        return all(
            _is_proven_non_executable_data_value(item, plain_data_types=plain_data_types)
            for item in value.elts
        )
    if isinstance(value, ast.Dict):
        items = (*value.keys, *value.values)
        return all(
            item is None
            or _is_proven_non_executable_data_value(item, plain_data_types=plain_data_types)
            for item in items
        )
    if isinstance(value, ast.Call):
        if _terminal_name(value.func) not in plain_data_types:
            return False
        return all(
            _is_proven_non_executable_data_value(item, plain_data_types=plain_data_types)
            for item in value.args
        ) and all(
            _is_proven_non_executable_data_value(keyword.value, plain_data_types=plain_data_types)
            for keyword in value.keywords
        )
    return False


def _is_non_executable_data_assignment(
    *,
    target: ast.Name,
    value: ast.AST,
    plain_data_types: set[str],
) -> bool:
    return _has_non_executable_data_suffix(target.id) and _is_proven_non_executable_data_value(
        value,
        plain_data_types=plain_data_types,
    )


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


def _function_raises_system_exit(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise) or _enclosing_function(child, parents) is not node:
            continue
        exc = child.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name) and exc.id == "SystemExit":
            return True
        if isinstance(exc, ast.Attribute) and exc.attr == "SystemExit":
            return True
    return False


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_singleton_is_not_none(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and _is_name(node.left, _CANONICAL_SINGLETON_NAME)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is None
    )


def _is_singleton_is_not_core(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and _is_name(node.left, _CANONICAL_SINGLETON_NAME)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and _is_name(node.comparators[0], "core")
    )


def _fail_closed_singleton_guard(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> ast.If | None:
    for statement in function.body:
        if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.BoolOp):
            continue
        if not isinstance(statement.test.op, ast.And) or len(statement.test.values) != 2:
            continue
        conditions = statement.test.values
        if not any(_is_singleton_is_not_none(item) for item in conditions):
            continue
        if not any(_is_singleton_is_not_core(item) for item in conditions):
            continue
        if any(
            isinstance(child, ast.Raise)
            and _enclosing_function(child, parents) is function
            and (
                (
                    isinstance(child.exc, ast.Call)
                    and _is_name(child.exc.func, "SystemExit")
                )
                or _is_name(child.exc, "SystemExit")
            )
            for child in ast.walk(statement)
        ):
            return statement
    return None


def _is_canonical_singleton_storage_assignment(
    *,
    relative: str,
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr,
    target: ast.Name,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if relative != _CANONICAL_SINGLETON_PATH or target.id != _CANONICAL_SINGLETON_NAME:
        return False
    value = getattr(node, "value", None)
    if not isinstance(value, ast.Name) or value.id != "core":
        return False
    function = _enclosing_function(node, parents)
    if function is None or function.name != _CANONICAL_SINGLETON_SETTER:
        return False
    parameters = (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
    if not any(parameter.arg == "core" for parameter in parameters):
        return False
    guard = _fail_closed_singleton_guard(function, parents=parents)
    if guard is None or not _function_raises_system_exit(function, parents=parents):
        return False
    return node in function.body and function.body.index(guard) < function.body.index(node)


def _module_exports(tree: ast.AST) -> set[str]:
    exported: set[str] = set()
    for node in getattr(tree, "body", ()):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, ast.List | ast.Set | ast.Tuple):
            continue
        exported.update(
            str(item.value)
            for item in node.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    return exported


def _authority_alias_assignments(node: ast.ClassDef) -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    for child in node.body:
        if not isinstance(child, ast.Assign) or not isinstance(child.value, ast.Name):
            continue
        for target in child.targets:
            if isinstance(target, ast.Name) and target.id in _AUTHORITY_METHODS:
                aliases.append((target.id, child.value.id))
    return aliases


def _has_bounded_regression_fixture_body(node: ast.ClassDef) -> bool:
    for child in node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            if child.name not in {"__init__", "evaluate"} or child.decorator_list:
                return False
            continue
        if (
            isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Constant)
            and isinstance(child.value.value, str)
        ):
            continue
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Constant):
            if (
                child.value.value is True
                and len(child.targets) == 1
                and isinstance(child.targets[0], ast.Name)
                and child.targets[0].id == _NON_RUNTIME_REGRESSION_FIXTURE_MARKER
            ):
                continue
            return False
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Name):
            if (
                child.value.id == "evaluate"
                and len(child.targets) == 1
                and isinstance(child.targets[0], ast.Name)
                and child.targets[0].id == "decide"
            ):
                continue
            return False
        return False
    return True


def _is_bounded_non_runtime_regression_fixture(
    *,
    relative: str,
    node: ast.ClassDef,
    exported_names: set[str],
) -> bool:
    if relative != _NON_RUNTIME_REGRESSION_FIXTURE_PATH:
        return False
    if node.name not in _NON_RUNTIME_REGRESSION_FIXTURE_NAMES or node.name in exported_names:
        return False
    if node.bases or node.keywords or node.decorator_list:
        return False
    if not _class_has_true_marker(node, _NON_RUNTIME_REGRESSION_FIXTURE_MARKER):
        return False
    methods = _class_method_names(node)
    if "evaluate" not in methods or methods - {"__init__", "evaluate"}:
        return False
    return (
        _authority_alias_assignments(node) == [("decide", "evaluate")]
        and _has_bounded_regression_fixture_body(node)
    )


def _is_registry_reference_accessor(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if node.name != "decision_core" or not isinstance(parents.get(node), ast.ClassDef):
        return False
    if node.decorator_list or node.args.vararg is not None or node.args.kwarg is not None:
        return False
    if node.args.defaults or any(default is not None for default in node.args.kw_defaults):
        return False
    parameters = (*node.args.posonlyargs, *node.args.args)
    if len(parameters) != 1 or node.args.kwonlyargs:
        return False
    receiver_name = parameters[0].arg
    if receiver_name not in {"self", "cls"}:
        return False

    statements = list(node.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    if len(statements) != 1 or not isinstance(statements[0], ast.Return):
        return False
    call = statements[0].value
    if not isinstance(call, ast.Call) or call.keywords or len(call.args) != 1:
        return False
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "get":
        return False
    registry = call.func.value
    if not (
        isinstance(registry, ast.Attribute)
        and registry.attr in {"registry", "_registry"}
        and isinstance(registry.value, ast.Name)
        and registry.value.id == receiver_name
    ):
        return False
    service_name = call.args[0]
    return isinstance(service_name, ast.Attribute) and service_name.attr == "DECISION_CORE"


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
    parents = _parent_map(tree)
    plain_data_types = _plain_frozen_data_type_names(tree)
    exported_names = _module_exports(tree)
    findings: list[auditor.Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if _is_fail_closed_runtime_decision_core_tripwire(relative=relative, node=node):
                continue
            if _is_bounded_non_runtime_regression_fixture(
                relative=relative,
                node=node,
                exported_names=exported_names,
            ):
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
            if _is_registry_reference_accessor(node, parents=parents):
                continue
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
            if _is_non_executable_data_assignment(
                target=target,
                value=value,
                plain_data_types=plain_data_types,
            ):
                continue
            if _is_canonical_singleton_storage_assignment(
                relative=relative,
                node=node,
                target=target,
                parents=parents,
            ):
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
