"""Reflection and mapping evidence helpers for authority access."""

from __future__ import annotations

import ast

from canon.anti_second_brain_rules import HARD_DECISION_AUTHORITY_METHODS
from tools._decision_authority_scan.contracts import (
    _MAPPING_METHODS,
    _REFLECTION_FACTORY_CALLS,
    _REFLECTION_LOOKUP_CALLS,
    _REFLECTION_MUTATION_CALLS,
)
from tools._decision_authority_scan.syntax import (
    _expression_path,
    _is_authority_access,
    _qualified_name,
    _receiver_looks_like_authority,
    _static_string,
)


def _reflection_lookup(
    node: ast.Call,
    aliases: dict[str, str],
) -> tuple[str, str | None] | None:
    qualified = _qualified_name(node.func, aliases)
    if qualified in _REFLECTION_LOOKUP_CALLS:
        if len(node.args) < 2:
            return None
        target = _expression_path(node.args[0], aliases)
        method = _static_string(node.args[1])
    elif qualified.endswith(".__getattribute__"):
        if len(node.args) >= 2:
            target = _expression_path(node.args[0], aliases)
            method = _static_string(node.args[1])
        elif node.args and isinstance(node.func, ast.Attribute):
            target = _expression_path(node.func.value, aliases)
            method = _static_string(node.args[0])
        else:
            return None
    else:
        return None

    if method is None and _receiver_looks_like_authority(target):
        return target, None
    if method is not None and _is_authority_access(target, method):
        return target, method
    return None


def _reflection_factory(
    node: ast.Call,
    aliases: dict[str, str],
    parents: dict[ast.AST, ast.AST],
) -> tuple[str, str | None] | None:
    qualified = _qualified_name(node.func, aliases)
    if qualified not in _REFLECTION_FACTORY_CALLS:
        return None
    method = _static_string(node.args[0]) if node.args else None

    if method in HARD_DECISION_AUTHORITY_METHODS:
        return qualified, method

    parent = parents.get(node)
    if not isinstance(parent, ast.Call) or parent.func is not node:
        return None
    if not parent.args:
        return None
    target = _expression_path(parent.args[0], aliases)
    if method is None and _receiver_looks_like_authority(target):
        return target, None
    if method is not None and _is_authority_access(target, method):
        return target, method
    return None


def _reflection_mutation(
    node: ast.Call,
    aliases: dict[str, str],
) -> tuple[str, str | None] | None:
    qualified = _qualified_name(node.func, aliases)
    if qualified not in _REFLECTION_MUTATION_CALLS:
        return None
    if len(node.args) < 2:
        return None
    target = _expression_path(node.args[0], aliases)
    method = _static_string(node.args[1])
    if method is None and _receiver_looks_like_authority(target):
        return target, None
    if method is not None and _is_authority_access(target, method):
        return target, method
    return None


def _is_decision_mapping(target: str) -> bool:
    return _receiver_looks_like_authority(target) and (
        "__dict__" in target
        or target.startswith("vars(")
        or target.endswith(".__dict__")
    )


def _mapping_access(
    node: ast.AST,
    aliases: dict[str, str],
) -> tuple[str, str | None, bool] | None:
    if isinstance(node, ast.Subscript):
        target = _expression_path(node.value, aliases)
        if not _is_decision_mapping(target):
            return None
        method = _static_string(node.slice)
        if method is None or _is_authority_access(target, method):
            mutation = isinstance(node.ctx, (ast.Store, ast.Del))
            return target, method, mutation
        return None

    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr not in _MAPPING_METHODS:
        return None
    target = _expression_path(node.func.value, aliases)
    if not _is_decision_mapping(target):
        return None
    method = _static_string(node.args[0]) if node.args else None
    if method is not None and not _is_authority_access(target, method):
        return None
    mutation = node.func.attr in {"pop", "setdefault", "update"}
    return target, method, mutation
