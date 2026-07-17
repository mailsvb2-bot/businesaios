from __future__ import annotations

import ast
from pathlib import Path

from canon.anti_second_brain_rules import (
    CANONICAL_DECISION_CORE_PATH,
    CANONICAL_DECISION_OWNER_PREFIXES,
    CONTEXTUAL_DECISION_AUTHORITY_METHODS,
    DECISION_AUTHORITY_METHODS,
    FORBIDDEN_DECISION_METHODS,
    HARD_DECISION_AUTHORITY_METHODS,
)
from scripts.ci.integrity.decision_authority_alias_rules import (
    AUTHORITY_METHODS as CI_AUTHORITY_METHODS,
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
    assert "decide" in HARD_DECISION_AUTHORITY_METHODS
    assert {"issue", "optimize"} <= CONTEXTUAL_DECISION_AUTHORITY_METHODS
    assert CI_AUTHORITY_METHODS is DECISION_AUTHORITY_METHODS


def test_only_file_exact_production_paths_own_decision_authority() -> None:
    assert CANONICAL_DECISION_CORE_PATH in CANONICAL_DECISION_OWNER_PREFIXES
    assert "runtime/decision_gateway.py" in CANONICAL_DECISION_OWNER_PREFIXES
    assert "runtime/decision_path_lock.py" in CANONICAL_DECISION_OWNER_PREFIXES
    for delegated_path in (
        "application/headless/decision_gateway.py",
        "demand_decision/canonical_decision_bridge.py",
    ):
        assert delegated_path not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "core/ai/" not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "application/decision_runtime/" not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "application/headless/" not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "demand_decision/" not in CANONICAL_DECISION_OWNER_PREFIXES


def test_exact_runtime_owners_retain_single_path_markers() -> None:
    expected = {
        "runtime/decision_gateway.py": {
            "CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH",
            "CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
            "CANON_RUNTIME_DECISION_GATEWAY_BINDS_REGISTERED_SINGLETON",
            "CANON_RUNTIME_DECISION_GATEWAY_REJECTS_SYNTHETIC_ENVELOPES",
            "CANON_RUNTIME_DECISION_GATEWAY_NO_STRUCTURED_ALT_ISSUER",
        },
        "runtime/decision_path_lock.py": {
            "CANON_DECISION_PATH_LOCK_SINGLE_OWNER",
            "CANON_DECISION_PATH_LOCK_NO_DECISION_LOGIC",
            "CANON_DECISION_PATH_LOCK_BINDS_REGISTERED_SINGLETON",
        },
    }

    for relative, required in expected.items():
        assert required <= _true_markers(_tree(relative)), relative


def test_headless_gateway_is_a_pure_runtime_delegate() -> None:
    relative = "application/headless/decision_gateway.py"
    tree = _tree(relative)
    markers = _true_markers(tree)
    assert {
        "CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH",
        "CANON_HEADLESS_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC",
        "CANON_HEADLESS_DECISION_GATEWAY_DELEGATES_TO_RUNTIME",
    } <= markers
    assert "CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER" not in markers

    ingress = _class(tree, "HeadlessDecisionIngress")
    issue = _function(ingress.body, "issue")
    direct_authority_calls = [
        node
        for node in ast.walk(issue)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"issue", "decide", "optimize"}
    ]
    assert direct_authority_calls == []
    delegated_calls = [
        node
        for node in ast.walk(issue)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "issue_runtime_decision"
    ]
    assert len(delegated_calls) == 1


def test_demand_bridge_issues_only_a_canonical_world_state() -> None:
    relative = "demand_decision/canonical_decision_bridge.py"
    tree = _tree(relative)
    assert {
        "CANON_DEMAND_BRIDGE_ADAPTS_SIGNED_ROUTE_DECISION"
    } <= _true_markers(tree)
    bridge = _class(tree, "CanonicalDemandDecisionBridge")
    issue_decision = _function(bridge.body, "_issue_route_decision")

    delegated_calls = [
        node
        for node in ast.walk(issue_decision)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "issue_runtime_decision"
    ]
    assert len(delegated_calls) == 1

    forbidden_calls = [
        node
        for node in ast.walk(issue_decision)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"issue", "decide", "optimize"}
    ]
    assert forbidden_calls == []


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


def test_recommendation_pipeline_never_issues_a_sovereign_decision() -> None:
    relative = "orchestration/decision_pipeline.py"
    tree = _tree(relative)
    assert {
        "CANON_DECISION_PIPELINE_RECOMMENDATION_ONLY",
        "CANON_DECISION_PIPELINE_NO_SOVEREIGN_ISSUANCE",
    } <= _true_markers(tree)
    pipeline = _class(tree, "DecisionPipeline")
    run = _function(pipeline.body, "run")

    authority_calls = [
        node
        for node in ast.walk(run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"issue", "decide", "optimize"}
    ]
    assert authority_calls == []
    selection_calls = [
        node
        for node in ast.walk(run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "select_action"
    ]
    assert len(selection_calls) == 1
