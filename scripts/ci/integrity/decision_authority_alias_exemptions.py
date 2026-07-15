from __future__ import annotations

import ast

from scripts.ci.integrity.decision_authority_alias_rules import (
    AUTHORITY_METHODS,
    class_method_names,
    enclosing_function,
)

_RUNTIME_DECISION_CORE_TRIPWIRE_PATH = "boot/runtime_service_contracts.py"
_RUNTIME_DECISION_CORE_TRIPWIRE_NAME = "RuntimeDecisionCore"
_RUNTIME_DECISION_CORE_TRIPWIRE_MARKER = (
    "CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE"
)
_CANONICAL_SINGLETON_PATH = "core/ai/__init__.py"
_CANONICAL_SINGLETON_NAME = "_DECISION_CORE_SINGLETON"
_CANONICAL_SINGLETON_SETTER = "set_decision_core_singleton"
_NON_RUNTIME_REGRESSION_FIXTURE_PATH = (
    "formal/regression_gate/project_snapshot_bundle.py"
)
_NON_RUNTIME_REGRESSION_FIXTURE_MARKER = "CANON_NON_RUNTIME_REGRESSION_FIXTURE"
_NON_RUNTIME_REGRESSION_FIXTURE_NAMES = frozenset(
    {"_RejectingDecisionCore", "_SelectingDecisionCore"}
)


def class_has_true_marker(node: ast.ClassDef, marker: str) -> bool:
    for child in node.body:
        if not isinstance(child, ast.Assign):
            continue
        if not isinstance(child.value, ast.Constant) or child.value.value is not True:
            continue
        if any(
            isinstance(target, ast.Name) and target.id == marker
            for target in child.targets
        ):
            return True
    return False


def init_raises_runtime_error(node: ast.ClassDef) -> bool:
    init = next(
        (
            child
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            and child.name == "__init__"
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


def is_fail_closed_runtime_decision_core_tripwire(
    *,
    relative: str,
    node: ast.ClassDef,
) -> bool:
    if (
        relative != _RUNTIME_DECISION_CORE_TRIPWIRE_PATH
        or node.name != _RUNTIME_DECISION_CORE_TRIPWIRE_NAME
    ):
        return False
    methods = class_method_names(node)
    return (
        class_has_true_marker(node, _RUNTIME_DECISION_CORE_TRIPWIRE_MARKER)
        and init_raises_runtime_error(node)
        and not (methods & AUTHORITY_METHODS)
    )


def function_raises_system_exit(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    for child in ast.walk(node):
        if (
            not isinstance(child, ast.Raise)
            or enclosing_function(child, parents) is not node
        ):
            continue
        exc = child.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name) and exc.id == "SystemExit":
            return True
        if isinstance(exc, ast.Attribute) and exc.attr == "SystemExit":
            return True
    return False


def is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def is_singleton_is_not_none(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and is_name(node.left, _CANONICAL_SINGLETON_NAME)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is None
    )


def is_singleton_is_not_core(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and is_name(node.left, _CANONICAL_SINGLETON_NAME)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and is_name(node.comparators[0], "core")
    )


def fail_closed_singleton_guard(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> ast.If | None:
    for statement in function.body:
        if not isinstance(statement, ast.If) or not isinstance(
            statement.test,
            ast.BoolOp,
        ):
            continue
        if not isinstance(statement.test.op, ast.And) or len(
            statement.test.values
        ) != 2:
            continue
        conditions = statement.test.values
        if not any(is_singleton_is_not_none(item) for item in conditions):
            continue
        if not any(is_singleton_is_not_core(item) for item in conditions):
            continue
        if any(
            isinstance(child, ast.Raise)
            and enclosing_function(child, parents) is function
            and (
                (
                    isinstance(child.exc, ast.Call)
                    and is_name(child.exc.func, "SystemExit")
                )
                or is_name(child.exc, "SystemExit")
            )
            for child in ast.walk(statement)
        ):
            return statement
    return None


def is_canonical_singleton_storage_assignment(
    *,
    relative: str,
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr,
    target: ast.Name,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if (
        relative != _CANONICAL_SINGLETON_PATH
        or target.id != _CANONICAL_SINGLETON_NAME
    ):
        return False
    value = getattr(node, "value", None)
    if not isinstance(value, ast.Name) or value.id != "core":
        return False
    function = enclosing_function(node, parents)
    if function is None or function.name != _CANONICAL_SINGLETON_SETTER:
        return False
    parameters = (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    )
    if not any(parameter.arg == "core" for parameter in parameters):
        return False
    guard = fail_closed_singleton_guard(function, parents=parents)
    if guard is None or not function_raises_system_exit(function, parents=parents):
        return False
    return node in function.body and function.body.index(guard) < function.body.index(
        node
    )


def module_exports(tree: ast.AST) -> set[str]:
    exported: set[str] = set()
    for node in getattr(tree, "body", ()):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.List | ast.Set | ast.Tuple):
            continue
        exported.update(
            str(item.value)
            for item in node.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    return exported


def authority_alias_assignments(node: ast.ClassDef) -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    for child in node.body:
        if not isinstance(child, ast.Assign) or not isinstance(
            child.value,
            ast.Name,
        ):
            continue
        for target in child.targets:
            if isinstance(target, ast.Name) and target.id in AUTHORITY_METHODS:
                aliases.append((target.id, child.value.id))
    return aliases


def has_bounded_regression_fixture_body(node: ast.ClassDef) -> bool:
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


def is_bounded_non_runtime_regression_fixture(
    *,
    relative: str,
    node: ast.ClassDef,
    exported_names: set[str],
) -> bool:
    if relative != _NON_RUNTIME_REGRESSION_FIXTURE_PATH:
        return False
    if (
        node.name not in _NON_RUNTIME_REGRESSION_FIXTURE_NAMES
        or node.name in exported_names
    ):
        return False
    if node.bases or node.keywords or node.decorator_list:
        return False
    if not class_has_true_marker(node, _NON_RUNTIME_REGRESSION_FIXTURE_MARKER):
        return False
    methods = class_method_names(node)
    if "evaluate" not in methods or methods - {"__init__", "evaluate"}:
        return False
    return authority_alias_assignments(node) == [
        ("decide", "evaluate")
    ] and has_bounded_regression_fixture_body(node)


def is_registry_reference_accessor(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    if node.name != "decision_core" or not isinstance(parents.get(node), ast.ClassDef):
        return False
    if (
        node.decorator_list
        or node.args.vararg is not None
        or node.args.kwarg is not None
    ):
        return False
    if node.args.defaults or any(
        default is not None for default in node.args.kw_defaults
    ):
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


__all__ = [
    "is_bounded_non_runtime_regression_fixture",
    "is_canonical_singleton_storage_assignment",
    "is_fail_closed_runtime_decision_core_tripwire",
    "is_registry_reference_accessor",
    "module_exports",
]
