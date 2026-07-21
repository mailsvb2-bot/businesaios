"""Context-sensitive alias collection across nested AST scopes."""

from __future__ import annotations

import ast

from tools._decision_authority_scan.alias_scope import (
    _apply_alias_target,
    _comprehension_local_names,
    _scope_final_aliases,
    _scope_local_names,
)
from tools._decision_authority_scan.syntax import _qualified_name


class _AliasContextCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.contexts: dict[ast.AST, dict[str, str]] = {}
        self._scopes: list[
            tuple[str, dict[str, str], dict[str, str]]
        ] = [("module", {}, {})]

    @property
    def aliases(self) -> dict[str, str]:
        return self._scopes[-1][1]

    @property
    def closure_aliases(self) -> dict[str, str]:
        return self._scopes[-1][2]

    def _record(self, node: ast.AST) -> None:
        self.contexts[node] = dict(self.aliases)

    def _visit_annotations(
        self,
        arguments: ast.arguments,
        returns: ast.expr | None,
    ) -> None:
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ):
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if arguments.vararg and arguments.vararg.annotation is not None:
            self.visit(arguments.vararg.annotation)
        if arguments.kwarg and arguments.kwarg.annotation is not None:
            self.visit(arguments.kwarg.annotation)
        if returns is not None:
            self.visit(returns)

    def _body_base_aliases(self) -> dict[str, str]:
        if self._scopes[-1][0] != "class":
            return dict(self.closure_aliases)
        for kind, _current, closure in reversed(self._scopes[:-1]):
            if kind != "class":
                return dict(closure)
        return {}

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._record(node)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        self._visit_annotations(node.args, node.returns)

        inherited = self._body_base_aliases()
        for local_name in _scope_local_names(node):
            inherited.pop(local_name, None)
        closure = _scope_final_aliases(node.body, inherited)
        self._scopes.append(("function", inherited, closure))
        for statement in node.body:
            self.visit(statement)
        self._scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_Module(self, node: ast.Module) -> None:
        closure = _scope_final_aliases(node.body, {})
        self._scopes[-1] = ("module", {}, closure)
        self._record(node)
        for statement in node.body:
            self.visit(statement)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._record(node)
        inherited = self._body_base_aliases()
        for local_name in _scope_local_names(node):
            inherited.pop(local_name, None)
        self._scopes.append(("function", inherited, dict(inherited)))
        self.visit(node.body)
        self._scopes.pop()

    def _visit_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        value_nodes: tuple[ast.AST, ...],
    ) -> None:
        self._record(node)
        if not node.generators:
            for value_node in value_nodes:
                self.visit(value_node)
            return

        first, *remaining = node.generators
        self.visit(first.iter)
        inherited = dict(self.aliases)
        for local_name in _comprehension_local_names(node.generators):
            inherited.pop(local_name, None)

        self._scopes.append(("function", inherited, dict(inherited)))
        self.visit(first.target)
        for condition in first.ifs:
            self.visit(condition)
        for generator in remaining:
            self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        for value_node in value_nodes:
            self.visit(value_node)
        self._scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, (node.key, node.value))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node, (node.elt,))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

        inherited = dict(self.aliases)
        for local_name in _scope_local_names(node):
            inherited.pop(local_name, None)
        self._scopes.append(("class", inherited, dict(inherited)))
        for statement in node.body:
            self.visit(statement)
        self._scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", 1)[0]
            self.aliases[local_name] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)
        if not node.module:
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            self.aliases[alias.asname or alias.name] = (
                f"{node.module}.{alias.name}"
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record(node)
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)
        source = _qualified_name(node.value, self.aliases)
        for target in node.targets:
            _apply_alias_target(
                target=target,
                source=source,
                aliases=self.aliases,
            )

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record(node)
        if node.annotation is not None:
            self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        self.visit(node.target)
        source = (
            _qualified_name(node.value, self.aliases)
            if node.value is not None
            else ""
        )
        _apply_alias_target(
            target=node.target,
            source=source,
            aliases=self.aliases,
        )

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._record(node)
        self.visit(node.value)
        self.visit(node.target)
        source = _qualified_name(node.value, self.aliases)
        _apply_alias_target(
            target=node.target,
            source=source,
            aliases=self.aliases,
        )

    def generic_visit(self, node: ast.AST) -> None:
        self._record(node)
        super().generic_visit(node)


def _alias_contexts(tree: ast.AST) -> dict[ast.AST, dict[str, str]]:
    collector = _AliasContextCollector()
    collector.visit(tree)
    return collector.contexts
