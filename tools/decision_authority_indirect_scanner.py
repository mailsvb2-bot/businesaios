"""Single-owner scan for hidden decision-authority execution paths.

The scanner enforces exact production owner files, repository-wide source
coverage, lexical alias resolution, reflection paths, stored method references,
dynamic lookup or mutation, and mapping-based authority access.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from canon.anti_second_brain_rules import (
    CONTEXTUAL_DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_RECEIVER_TOKENS,
    HARD_DECISION_AUTHORITY_METHODS,
    is_canonical_decision_owner_path,
)

CANON_DECISION_AUTHORITY_INDIRECT_SCAN = True
CANON_LEXICAL_AUTHORITY_ALIAS_RESOLUTION = True

GLOBAL_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "venv",
}
ROOT_EXCLUDED_DIRS = {
    "artifacts",
    "build",
    "data",
    "dist",
    "htmlcov",
    "release_dist",
    "reports",
}

_REFLECTION_LOOKUP_CALLS = frozenset(
    {
        "getattr",
        "builtins.getattr",
        "inspect.getattr_static",
        "object.__getattribute__",
        "type.__getattribute__",
    }
)
_REFLECTION_FACTORY_CALLS = frozenset(
    {
        "operator.attrgetter",
        "operator.methodcaller",
    }
)
_REFLECTION_MUTATION_CALLS = frozenset(
    {
        "setattr",
        "builtins.setattr",
        "delattr",
        "builtins.delattr",
    }
)
_MAPPING_METHODS = frozenset(
    {
        "get",
        "pop",
        "setdefault",
        "update",
    }
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.detail}"


def _iter_python_files(root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        base = Path(directory)
        at_root = not base.relative_to(root).parts
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in GLOBAL_EXCLUDED_DIRS
            and not (at_root and name in ROOT_EXCLUDED_DIRS)
        )
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield base / filename


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
        elif isinstance(node, ast.AnnAssign):
            names.update(_bound_names_in_target(node.target))
        elif isinstance(node, ast.NamedExpr):
            names.update(_bound_names_in_target(node.target))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
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


def _scan_ast(
    *,
    rel: str,
    tree: ast.AST,
) -> list[Finding]:
    if is_canonical_decision_owner_path(rel):
        return []

    findings: list[Finding] = []
    parents = _parent_map(tree)
    aliases_by_node = _alias_contexts(tree)

    for node in ast.walk(tree):
        line = int(getattr(node, "lineno", 0) or 0)
        aliases = aliases_by_node.get(node, {})

        if isinstance(node, ast.ImportFrom):
            module_owner = str(node.module or "")
            for alias in node.names:
                if not alias.asname:
                    continue
                if _is_authority_access(module_owner, alias.name):
                    findings.append(
                        Finding(
                            "decision_authority_alias_import",
                            rel,
                            line,
                            f"{module_owner}.{alias.name} imported as "
                            f"{alias.asname}",
                        )
                    )

        if isinstance(node, ast.Name):
            if (
                isinstance(node.ctx, ast.Load)
                and node.id in HARD_DECISION_AUTHORITY_METHODS
                and not _is_direct_call_function(node, parents)
            ):
                findings.append(
                    Finding(
                        "decision_authority_name_reference",
                        rel,
                        line,
                        f"{node.id} stored or exposed outside a canonical owner",
                    )
                )

        if isinstance(node, ast.Attribute):
            owner = _expression_path(node.value, aliases)
            if (
                _is_authority_access(owner, node.attr)
                and not _is_direct_call_function(node, parents)
            ):
                findings.append(
                    Finding(
                        "decision_authority_method_reference",
                        rel,
                        line,
                        f"{owner}.{node.attr} stored or exposed outside "
                        "a canonical owner",
                    )
                )

        mapping = _mapping_access(node, aliases)
        if mapping is not None:
            target, method, mutation = mapping
            findings.append(
                Finding(
                    "decision_authority_mapping_mutation"
                    if mutation
                    else "decision_authority_mapping_lookup",
                    rel,
                    line,
                    f"{target}[{method or '<dynamic>'!r}] outside "
                    "a canonical owner",
                )
            )

        if not isinstance(node, ast.Call):
            continue

        owner, name = _call_name(node.func, aliases)
        if _is_authority_access(owner, name):
            target = f"{owner}.{name}" if owner else str(name)
            findings.append(
                Finding(
                    "decision_authority_call",
                    rel,
                    line,
                    f"{target}() outside a canonical owner",
                )
            )

        lookup = _reflection_lookup(node, aliases)
        if lookup is None:
            lookup = _reflection_factory(node, aliases, parents)
        if lookup is not None:
            target, method = lookup
            findings.append(
                Finding(
                    "decision_authority_dynamic_lookup",
                    rel,
                    line,
                    f"dynamic lookup of {target}.{method or '<dynamic>'}",
                )
            )

        mutation = _reflection_mutation(node, aliases)
        if mutation is not None:
            target, method = mutation
            findings.append(
                Finding(
                    "decision_authority_dynamic_mutation",
                    rel,
                    line,
                    f"dynamic mutation of {target}.{method or '<dynamic>'}",
                )
            )

    unique = {
        (item.code, item.path, item.line, item.detail): item
        for item in findings
    }
    return sorted(
        unique.values(),
        key=lambda item: (
            item.path,
            item.line,
            item.code,
            item.detail,
        ),
    )


def scan(root: Path | None = None) -> tuple[Finding, ...]:
    repo = (root or Path.cwd()).resolve()
    findings: list[Finding] = []
    for path in _iter_python_files(repo):
        rel = path.relative_to(repo).as_posix()
        if is_canonical_decision_owner_path(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(text, filename=rel)
        except (SyntaxError, ValueError):
            continue
        findings.extend(_scan_ast(rel=rel, tree=tree))

    unique = {
        (item.code, item.path, item.line, item.detail): item
        for item in findings
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.path,
                item.line,
                item.code,
                item.detail,
            ),
        )
    )


def main() -> int:
    findings = scan(Path.cwd())
    if not findings:
        print("decision authority indirect scan passed")
        return 0
    print(
        "decision authority indirect scan failed: "
        f"findings={len(findings)}"
    )
    for finding in findings[:80]:
        print(finding.format())
    if len(findings) > 80:
        print(f"... {len(findings) - 80} more finding(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
