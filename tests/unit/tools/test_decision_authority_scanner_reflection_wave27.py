from __future__ import annotations

import ast
from typing import cast

import tools.decision_authority_indirect_scanner as scanner


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _call(source: str) -> ast.Call:
    return cast(ast.Call, _expr(source))



def test_reflection_mapping_and_ast_scan_detect_all_indirect_authority_paths() -> None:
    aliases = {"op": "operator", "ga": "getattr", "sa": "setattr"}

    assert scanner._reflection_lookup(_call("ga(decision_core, 'decide')"), aliases) == ("decision_core", "decide")
    assert scanner._reflection_lookup(_call("getattr(decision_core)"), {}) is None
    assert scanner._reflection_lookup(_call("getattr(service, name)"), {}) is None
    assert scanner._reflection_lookup(_call("getattr(decision_core, name)"), {}) == ("decision_core", None)
    assert scanner._reflection_lookup(_call("decision_core.__getattribute__('decide')"), {}) == (
        "decision_core",
        "decide",
    )
    assert scanner._reflection_lookup(_call("object.__getattribute__(decision_core, 'decide')"), {}) == (
        "decision_core",
        "decide",
    )
    assert scanner._reflection_lookup(_call("service.__getattribute__(decision_core, 'decide')"), {}) == (
        "decision_core",
        "decide",
    )
    assert scanner._reflection_lookup(_call("service.__getattribute__()"), {}) is None
    assert scanner._reflection_lookup(_call("service()"), {}) is None

    factory_tree = ast.parse("op.attrgetter('decide')(decision_core)")
    factory = next(
        node for node in ast.walk(factory_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    parents = scanner._parent_map(factory_tree)
    assert scanner._reflection_factory(factory, aliases, parents) == ("operator.attrgetter", "decide")
    assert scanner._reflection_factory(_call("op.attrgetter('issue')"), aliases, {}) is None
    dynamic_tree = ast.parse("op.attrgetter(name)(decision_core)")
    dynamic_factory = next(
        node for node in ast.walk(dynamic_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert scanner._reflection_factory(dynamic_factory, aliases, scanner._parent_map(dynamic_tree)) == (
        "decision_core",
        None,
    )
    contextual_tree = ast.parse("op.attrgetter('issue')(decision_engine)")
    contextual_factory = next(
        node
        for node in ast.walk(contextual_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert scanner._reflection_factory(contextual_factory, aliases, scanner._parent_map(contextual_tree)) == (
        "decision_engine",
        "issue",
    )
    harmless_tree = ast.parse("op.attrgetter('issue')(certificate)")
    harmless_factory = next(
        node for node in ast.walk(harmless_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert scanner._reflection_factory(harmless_factory, aliases, scanner._parent_map(harmless_tree)) is None
    no_arg_tree = ast.parse("op.attrgetter('issue')()")
    no_arg_factory = next(
        node for node in ast.walk(no_arg_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert scanner._reflection_factory(no_arg_factory, aliases, scanner._parent_map(no_arg_tree)) is None
    assert scanner._reflection_factory(_call("factory('decide')"), aliases, {}) is None

    assert scanner._reflection_mutation(_call("sa(decision_core, 'decide', fn)"), aliases) == (
        "decision_core",
        "decide",
    )
    assert scanner._reflection_mutation(_call("setattr(decision_core, name, fn)"), {}) == ("decision_core", None)
    assert scanner._reflection_mutation(_call("setattr(service, 'other', fn)"), {}) is None
    assert scanner._reflection_mutation(_call("setattr(service)"), {}) is None
    assert scanner._reflection_mutation(_call("factory(service, 'decide')"), {}) is None

    assert scanner._is_decision_mapping("decision_core.__dict__") is True
    assert scanner._is_decision_mapping("vars(decision_core)") is True
    assert scanner._is_decision_mapping("service.__dict__") is False

    assert scanner._mapping_access(_expr("decision_core.__dict__['decide']"), {}) == (
        "decision_core.__dict__",
        "decide",
        False,
    )
    assert scanner._mapping_access(ast.parse("decision_core.__dict__['decide'] = fn").body[0].targets[0], {}) == (
        "decision_core.__dict__",
        "decide",
        True,
    )  # type: ignore[attr-defined]
    assert scanner._mapping_access(_expr("decision_core.__dict__[name]"), {}) == ("decision_core.__dict__", None, False)
    assert scanner._mapping_access(_expr("service.__dict__['decide']"), {}) is None
    assert scanner._mapping_access(_expr("decision_core.__dict__['other']"), {}) is None
    assert scanner._mapping_access(_call("decision_core.__dict__.get('decide')"), {}) == (
        "decision_core.__dict__",
        "decide",
        False,
    )
    assert scanner._mapping_access(_call("decision_core.__dict__.pop('decide')"), {}) == (
        "decision_core.__dict__",
        "decide",
        True,
    )
    assert scanner._mapping_access(_call("decision_core.__dict__.update()"), {}) == (
        "decision_core.__dict__",
        None,
        True,
    )
    assert scanner._mapping_access(_call("decision_core.__dict__.keys()"), {}) is None
    assert scanner._mapping_access(_call("service.__dict__.get('decide')"), {}) is None
    assert scanner._mapping_access(_call("decision_core.__dict__.get('other')"), {}) is None
    assert scanner._mapping_access(_expr("plain"), {}) is None

    source = """
from core.ai.decision_core import decide as hidden_decide
from core.ai.decision_core import decide
from certificate import issue as hidden_issue
import operator as op
alias = hidden_decide
method = decision_core.decide
decide
hidden_decide(payload)
decision_core.issue(payload)
getattr(decision_core, 'decide')
getattr(decision_core, dynamic_name)
op.attrgetter('decide')(decision_core)
setattr(decision_core, 'decide', replacement)
decision_core.__dict__['decide']
decision_core.__dict__.pop('decide')
"""
    findings = scanner._scan_ast(rel="core/example.py", tree=ast.parse(source))
    codes = {item.code for item in findings}
    assert {
        "decision_authority_alias_import",
        "decision_authority_name_reference",
        "decision_authority_method_reference",
        "decision_authority_call",
        "decision_authority_dynamic_lookup",
        "decision_authority_dynamic_mutation",
        "decision_authority_mapping_lookup",
        "decision_authority_mapping_mutation",
    } <= codes
    assert findings == sorted(findings, key=lambda item: (item.path, item.line, item.code, item.detail))
    assert scanner._scan_ast(rel="core/ai/decision_core.py", tree=ast.parse(source)) == []
