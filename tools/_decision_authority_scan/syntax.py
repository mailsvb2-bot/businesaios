"""Pure AST expression and authority-access helpers."""

from __future__ import annotations

import ast

from canon.anti_second_brain_rules import (
    CONTEXTUAL_DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_RECEIVER_TOKENS,
    HARD_DECISION_AUTHORITY_METHODS,
)


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _static_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant):
                return None
            if not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _qualified_name(node.value, aliases)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _expression_path(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _expression_path(node.value, aliases)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        base = _qualified_name(node.func, aliases)
        first = _static_string(node.args[0]) if node.args else None
        if first is not None:
            argument = repr(first)
        elif node.args:
            argument = _expression_path(node.args[0], aliases)
        else:
            argument = ""
        return f"{base}({argument})" if base else f"({argument})"
    if isinstance(node, ast.Subscript):
        base = _expression_path(node.value, aliases)
        key = _static_string(node.slice)
        return f"{base}[{key!r}]" if key is not None else f"{base}[]"
    return ""


def _call_name(
    node: ast.AST,
    aliases: dict[str, str],
) -> tuple[str | None, str | None]:
    if isinstance(node, ast.Attribute):
        owner = _expression_path(node.value, aliases)
        return owner or None, node.attr
    qualified = _qualified_name(node, aliases)
    if not qualified:
        return None, None
    if "." not in qualified:
        return None, qualified
    owner, name = qualified.rsplit(".", 1)
    return owner, name


def _normalized_receiver(owner: str | None) -> str:
    return "".join(
        character
        for character in str(owner or "").casefold()
        if character.isalnum()
    )


def _receiver_looks_like_authority(owner: str | None) -> bool:
    normalized = _normalized_receiver(owner)
    return any(
        token in normalized for token in DECISION_AUTHORITY_RECEIVER_TOKENS
    )


def _is_authority_access(owner: str | None, method: str | None) -> bool:
    if method not in DECISION_AUTHORITY_METHODS:
        return False
    if method in HARD_DECISION_AUTHORITY_METHODS:
        return True
    return (
        method in CONTEXTUAL_DECISION_AUTHORITY_METHODS
        and _receiver_looks_like_authority(owner)
    )


def _is_direct_call_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    parent = parents.get(node)
    return isinstance(parent, ast.Call) and parent.func is node


def _bound_names_in_target(target: ast.AST) -> set[str]:
    return {
        child.id
        for child in ast.walk(target)
        if isinstance(child, ast.Name)
        and isinstance(child.ctx, (ast.Store, ast.Del))
    }
