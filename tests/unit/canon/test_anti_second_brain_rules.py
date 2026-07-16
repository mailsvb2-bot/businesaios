from __future__ import annotations

from canon.anti_second_brain_rules import (
    CANONICAL_DECISION_OWNER_PREFIXES,
    DECISION_AUTHORITY_METHODS,
    FORBIDDEN_DECISION_METHODS,
)


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
    assert "application/headless/decision_gateway.py" in CANONICAL_DECISION_OWNER_PREFIXES
    assert "demand_decision/canonical_decision_bridge.py" in CANONICAL_DECISION_OWNER_PREFIXES
    assert "application/headless/" not in CANONICAL_DECISION_OWNER_PREFIXES
    assert "demand_decision/" not in CANONICAL_DECISION_OWNER_PREFIXES
