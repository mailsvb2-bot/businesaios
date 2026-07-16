from __future__ import annotations

import ast
import re

AUTHORITY_METHODS = frozenset({"decide", "issue", "optimize"})

_AUTHORITY_TOKENS = (
    "decisioncore",
    "decisionengine",
    "plannerengine",
    "secondbrain",
    "shadowbrain",
    "alternatebrain",
    "localbrain",
)
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
_NON_EXECUTABLE_DATA_SUFFIXES = ("_DEPS", "_IMPORT_PATH", "_SYNONYMS")


def normalized(name: str) -> str:
    return "".join(ch for ch in str(name or "").casefold() if ch.isalnum())


def normalized_type_stem(name: str) -> str:
    return re.sub(r"v?\d+$", "", normalized(name))


def looks_like_decision_authority_alias(name: str, executable_names: set[str]) -> bool:
    text = str(name or "")
    if text in executable_names:
        return True

    # Snake-case names such as `decision_core` are dependency/instance bindings,
    # not exported authority type surfaces. Assignment/import checks target
    # exported aliases such as RuntimeDecisionCore or DecisionEngine.
    if not any(ch.isupper() for ch in text):
        return False

    normalized_name = normalized(text)
    return any(token in normalized_name for token in _AUTHORITY_TOKENS)


def is_authority_type_definition_name(name: str, executable_names: set[str]) -> bool:
    if str(name) in executable_names:
        return True
    stem = normalized_type_stem(name)
    return any(stem.endswith(token) for token in _AUTHORITY_TOKENS)


def is_authority_function_definition_name(name: str, executable_names: set[str]) -> bool:
    text = str(name or "")
    if text in executable_names:
        return True

    stem = normalized_type_stem(text)
    executable_stems = {normalized_type_stem(item) for item in executable_names}
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


def class_method_names(node: ast.ClassDef) -> set[str]:
    return {
        child.name
        for child in node.body
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef):
            return parent
        parent = parents.get(parent)
    return None


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def method_is_abstract_contract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    decorator_names = {decorator_name(item) for item in node.decorator_list}
    if any(name.endswith("abstractmethod") for name in decorator_names):
        return True

    statements = list(node.body)
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    if len(statements) != 1:
        return False

    statement = statements[0]
    if isinstance(statement, ast.Pass):
        return True
    if (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    ):
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


def is_pure_authority_interface(node: ast.ClassDef) -> bool:
    if not node.name.endswith(_INTERFACE_SUFFIXES):
        return False
    authority_methods = [
        child
        for child in node.body
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        and child.name in AUTHORITY_METHODS
    ]
    return bool(authority_methods) and all(
        method_is_abstract_contract(method) for method in authority_methods
    )


def is_plain_frozen_data_class(node: ast.ClassDef) -> bool:
    if node.bases or node.keywords or len(node.decorator_list) != 1:
        return False
    frozen_dataclass = False
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator_name(
            decorator.func
        ).endswith("dataclass"):
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


def plain_frozen_data_type_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in getattr(tree, "body", ())
        if isinstance(node, ast.ClassDef) and is_plain_frozen_data_class(node)
    }


def has_non_executable_data_suffix(name: str) -> bool:
    return str(name or "").upper().endswith(_NON_EXECUTABLE_DATA_SUFFIXES)


def terminal_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def is_proven_non_executable_data_value(
    value: ast.AST,
    *,
    plain_data_types: set[str],
) -> bool:
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Name | ast.Attribute):
        return has_non_executable_data_suffix(terminal_name(value))
    if isinstance(value, ast.List | ast.Set | ast.Tuple):
        return all(
            is_proven_non_executable_data_value(
                item,
                plain_data_types=plain_data_types,
            )
            for item in value.elts
        )
    if isinstance(value, ast.Dict):
        items = (*value.keys, *value.values)
        return all(
            item is None
            or is_proven_non_executable_data_value(
                item,
                plain_data_types=plain_data_types,
            )
            for item in items
        )
    if isinstance(value, ast.Call):
        if terminal_name(value.func) not in plain_data_types:
            return False
        return all(
            is_proven_non_executable_data_value(
                item,
                plain_data_types=plain_data_types,
            )
            for item in value.args
        ) and all(
            is_proven_non_executable_data_value(
                keyword.value,
                plain_data_types=plain_data_types,
            )
            for keyword in value.keywords
        )
    return False


def is_non_executable_data_assignment(
    *,
    target: ast.Name,
    value: ast.AST,
    plain_data_types: set[str],
) -> bool:
    return has_non_executable_data_suffix(
        target.id
    ) and is_proven_non_executable_data_value(
        value,
        plain_data_types=plain_data_types,
    )


def assigned_names(
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr,
) -> tuple[ast.Name, ...]:
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


def value_can_expose_executable(value: ast.AST) -> bool:
    if isinstance(value, ast.Constant):
        return False
    if isinstance(value, ast.Name | ast.Attribute | ast.Call | ast.Lambda | ast.Subscript):
        return True
    if isinstance(value, ast.IfExp):
        return value_can_expose_executable(value.body) or value_can_expose_executable(
            value.orelse
        )
    if isinstance(value, ast.List | ast.Set | ast.Tuple):
        return any(value_can_expose_executable(item) for item in value.elts)
    if isinstance(value, ast.Dict):
        return any(
            item is not None and value_can_expose_executable(item)
            for item in value.values
        )
    return False


__all__ = [
    "AUTHORITY_METHODS",
    "assigned_names",
    "class_method_names",
    "enclosing_function",
    "is_authority_function_definition_name",
    "is_authority_type_definition_name",
    "is_non_executable_data_assignment",
    "is_pure_authority_interface",
    "looks_like_decision_authority_alias",
    "parent_map",
    "plain_frozen_data_type_names",
    "value_can_expose_executable",
]
