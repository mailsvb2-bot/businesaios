"""Lexical alias resolution for scanner scopes."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from tools._decision_authority_scan.syntax import (
    _bound_names_in_target,
    _qualified_name,
)


def _scope_local_names(
    scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef,
) -> set[str]:
    names: set[str] = set()
    if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        arguments = scope.args
        names.update(argument.arg for argument in arguments.posonlyargs)
        names.update(argument.arg for argument in arguments.args)
        names.update(argument.arg for argument in arguments.kwonlyargs)
        if arguments.vararg is not None:
            names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            names.add(arguments.kwarg.arg)

    body = scope.body if not isinstance(scope, ast.Lambda) else ()
    global_names: set[str] = set()
    nonlocal_names: set[str] = set()

    def walk_statement(node: ast.AST) -> None:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ) and node is not scope:
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                names.add(node.name)
            return
        if isinstance(node, ast.Global):
            global_names.update(node.names)
            return
        if isinstance(node, ast.Nonlocal):
            nonlocal_names.update(node.names)
            return
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_bound_names_in_target(target))
        elif isinstance(
            node,
            (ast.AnnAssign, ast.NamedExpr, ast.For, ast.AsyncFor),
        ):
            names.update(_bound_names_in_target(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_bound_names_in_target(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)

        for child in ast.iter_child_nodes(node):
            walk_statement(child)

    for statement in body:
        walk_statement(statement)
    names.difference_update(global_names)
    names.difference_update(nonlocal_names)
    return names


def _apply_alias_target(
    *,
    target: ast.AST,
    source: str,
    aliases: dict[str, str],
) -> None:
    for name in _bound_names_in_target(target):
        if source and isinstance(target, ast.Name):
            aliases[name] = source
        else:
            aliases.pop(name, None)


def _scope_final_aliases(
    body: Iterable[ast.stmt],
    base_aliases: dict[str, str],
) -> dict[str, str]:
    aliases = dict(base_aliases)

    def process(node: ast.AST) -> None:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                aliases.pop(node.name, None)
            return
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                aliases[local_name] = alias.name
            return
        if isinstance(node, ast.ImportFrom):
            if not node.module:
                return
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = (
                        f"{node.module}.{alias.name}"
                    )
            return
        if isinstance(node, ast.Assign):
            source = _qualified_name(node.value, aliases)
            for target in node.targets:
                _apply_alias_target(
                    target=target,
                    source=source,
                    aliases=aliases,
                )
        elif isinstance(node, ast.AnnAssign):
            source = (
                _qualified_name(node.value, aliases)
                if node.value is not None
                else ""
            )
            _apply_alias_target(
                target=node.target,
                source=source,
                aliases=aliases,
            )
        elif isinstance(node, ast.NamedExpr):
            source = _qualified_name(node.value, aliases)
            _apply_alias_target(
                target=node.target,
                source=source,
                aliases=aliases,
            )
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _apply_alias_target(
                target=node.target,
                source="",
                aliases=aliases,
            )
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    _apply_alias_target(
                        target=item.optional_vars,
                        source="",
                        aliases=aliases,
                    )
        elif isinstance(node, ast.ExceptHandler) and node.name:
            aliases.pop(node.name, None)

        for child in ast.iter_child_nodes(node):
            process(child)

    for statement in body:
        process(statement)
    return aliases


def _comprehension_local_names(
    generators: list[ast.comprehension],
) -> set[str]:
    names: set[str] = set()
    for generator in generators:
        names.update(_bound_names_in_target(generator.target))
    return names
