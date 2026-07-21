from __future__ import annotations

import ast
from typing import cast

import tools.decision_authority_indirect_scanner as scanner


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _call(source: str) -> ast.Call:
    return cast(ast.Call, _expr(source))



def test_scope_and_alias_collection_cover_all_binding_forms() -> None:
    source = """
external = object()
def outer(posonly, /, arg: external = external, *args, kw: external = external, **kwargs) -> external:
    global global_name
    nonlocal_name = 1
    import pkg.mod
    import other as alias
    from mod import item, other as renamed
    from mod import *
    assigned = external
    annotated: int = external
    if (named := external):
        pass
    for loop in values:
        pass
    async for async_loop in values:
        pass
    with ctx() as managed:
        pass
    with ctx():
        pass
    async with ctx() as async_managed:
        pass
    try:
        pass
    except Exception as caught:
        pass
    def nested():
        hidden = 1
    class Nested:
        hidden = 1
    lambda value: value
    [value for value in values]
    return assigned
"""
    module = ast.parse(source)
    fn = next(node for node in module.body if isinstance(node, ast.FunctionDef))
    names = scanner._scope_local_names(fn)
    assert {
        "posonly",
        "arg",
        "args",
        "kw",
        "kwargs",
        "nonlocal_name",
        "pkg",
        "alias",
        "item",
        "renamed",
        "assigned",
        "annotated",
        "named",
        "loop",
        "async_loop",
        "managed",
        "async_managed",
        "caught",
        "nested",
        "Nested",
    } <= names
    assert "global_name" not in names

    nonlocal_module = ast.parse(
        "def parent():\n    captured = 1\n    def child():\n        nonlocal captured\n        return captured\n"
    )
    child = next(
        node for node in ast.walk(nonlocal_module) if isinstance(node, ast.FunctionDef) and node.name == "child"
    )
    assert "captured" not in scanner._scope_local_names(child)

    lambda_node = next(node for node in ast.walk(ast.parse("f = lambda x, *a, **k: x")) if isinstance(node, ast.Lambda))
    assert scanner._scope_local_names(lambda_node) == {"x", "a", "k"}

    aliases = {"x": "owner.decide"}
    scanner._apply_alias_target(target=ast.Name(id="y", ctx=ast.Store()), source="owner.decide", aliases=aliases)
    assert aliases["y"] == "owner.decide"
    destructuring_target = ast.parse("a, *b = values").body[0].targets[0]  # type: ignore[attr-defined]
    scanner._apply_alias_target(target=destructuring_target, source="owner.decide", aliases=aliases)
    assert "a" not in aliases and "b" not in aliases

    body = ast.parse("""
import package.mod
import other.mod as om
from package import item, other as renamed
from . import relative
from package import *
value = om.owner
(a, b) = pair
annotated: object = item
empty: object
(named := renamed)
for loop in values:
    pass
with ctx() as managed:
    pass
with ctx():
    pass
try:
    pass
except Exception as caught:
    pass
def old():
    pass
class Local:
    pass
""").body
    final = scanner._scope_final_aliases(body, {"old": "pkg.old", "loop": "pkg.loop", "caught": "pkg.caught"})
    assert final["package"] == "package.mod"
    assert final["om"] == "other.mod"
    assert final["item"] == "package.item"
    assert final["renamed"] == "package.other"
    assert final["value"] == "other.mod.owner"
    assert final["annotated"] == "package.item"
    assert final["named"] == "package.other"
    for removed in ("a", "b", "empty", "loop", "managed", "caught", "old", "Local"):
        assert removed not in final

    comp = cast(ast.ListComp, _expr("[(a, b) for a, b in rows]"))
    assert scanner._comprehension_local_names(comp.generators) == {"a", "b"}

    relative_contexts = scanner._alias_contexts(
        ast.parse("from . import relative\nfrom package import *\ndef required_kwonly(*, value):\n    return value\n")
    )
    assert relative_contexts

    contexts = scanner._alias_contexts(
        ast.parse("""
import operator as op
from core.ai import decision_core as dc
alias = dc.DecisionCore
ann: dc.DecisionCore = alias
empty: dc.DecisionCore
named = (walrus := alias)
@decorator(alias)
def function(arg: alias = alias, *args: alias, kw: alias = alias, **kwargs: alias) -> alias:
    local = alias
    return lambda inner: local
@decorator(alias)
class Example(alias, metaclass=alias):
    inside = alias
    values = [alias for alias in source if alias]
    sets = {alias for first in source for alias in first if alias}
    mapping = {alias: alias for alias in source}
    generator = (alias for alias in source)
async def async_function(value=alias):
    return alias
""")
    )
    assert contexts
    assert any("dc" in value for value in contexts.values())
    assert any("alias" in value for value in contexts.values())

    collector_only_class = scanner._AliasContextCollector()
    collector_only_class._scopes = [("class", {}, {})]
    assert collector_only_class._body_base_aliases() == {}
    collector_nested_class = scanner._AliasContextCollector()
    collector_nested_class._scopes = [("module", {}, {"outer": "pkg.outer"}), ("class", {}, {}), ("class", {}, {})]
    assert collector_nested_class._body_base_aliases() == {"outer": "pkg.outer"}

    empty = ast.ListComp(elt=ast.Constant(1), generators=[])
    collector = scanner._AliasContextCollector()
    collector.visit(empty)
    assert empty in collector.contexts
    defensive_annassign = ast.AnnAssign(
        target=ast.Name(id="value", ctx=ast.Store()),
        annotation=None,  # type: ignore[arg-type]
        value=ast.Name(id="alias", ctx=ast.Load()),
        simple=1,
    )
    collector.visit(defensive_annassign)
    assert defensive_annassign in collector.contexts
