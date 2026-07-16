from __future__ import annotations

import ast
from pathlib import Path

from canon.anti_second_brain_rules import (
    CANONICAL_DECISION_OWNER_PREFIXES,
    DECISION_AUTHORITY_METHODS,
    FORBIDDEN_DECISION_METHODS,
)

ROOT = Path(__file__).resolve().parents[3]


def _tree(relative: str) -> ast.Module:
    path = ROOT / relative
    return ast.parse(path.read_text(encoding="utf-8"), filename=relative)


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _function(
    nodes: list[ast.stmt],
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in nodes
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _true_markers(tree: ast.Module) -> set[str]:
    markers: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if node.value.value is not True:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                markers.add(target.id)
    return markers


def test_historical_forbidden_method_contract_is_preserved() -> None:
    assert FORBIDDEN_DECISION_METHODS == {
        "decide_strategy",
        "emit_final_action",
        "issue_strategy",
        "select_final_action",
    }


def test_canonical_authority_vocabulary_contains_legacy_contract() -> None:
    assert FORBIDDEN_DECISION_METHODS <= DECISION_AUTHORITY_METHODS
    assert {"decide", "issue", "optimize"} <= DECISION_AUTHORITY_METHODS


def test_only_exact_gateway_paths_expand_the_canonical_owner_surface() -> None:
    assert (
        "application/headless/decision_gateway.py"
        in CANONICAL_DECISION_OWNER_PREFIXES
    )
    assert (
        "demand_decision/canonical_decision_bridge.py"
        in CANONICAL_DECISION_OWNER_PREFIXES
    )
    assert "application/headless/" not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "demand_decision/" not in CANONICAL_DECISION_OWNER_PREFIXES


def test_exact_gateway_exceptions_retain_single_path_markers() -> None:
    expected = {
        "application/headless/decision_gateway.py": {
            "CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH",
            "CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
        },
        "runtime/decision_gateway.py": {
            "CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH",
            "CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
        },
        "runtime/decision_path_lock.py": {
            "CANON_DECISION_PATH_LOCK_SINGLE_OWNER",
            "CANON_DECISION_PATH_LOCK_NO_DECISION_LOGIC",
        },
    }

    for relative, required in expected.items():
        assert required <= _true_markers(_tree(relative)), relative


def test_demand_bridge_decide_alias_is_forward_only() -> None:
    tree = _tree("demand_decision/canonical_decision_bridge.py")
    bridge = _class(tree, "CanonicalDemandDecisionBridge")
    aliases = [
        node
        for node in bridge.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "decide"
            for target in node.targets
        )
    ]
    assert len(aliases) == 1
    assert isinstance(aliases[0].value, ast.Name)
    assert aliases[0].value.id == "evaluate"

    evaluate = _function(bridge.body, "evaluate")
    assert len(evaluate.body) == 1
    statement = evaluate.body[0]
    assert isinstance(statement, ast.Return)
    assert isinstance(statement.value, ast.Call)
    assert isinstance(statement.value.func, ast.Attribute)
    assert isinstance(statement.value.func.value, ast.Name)
    assert statement.value.func.value.id == "self"
    assert statement.value.func.attr == "issue"
