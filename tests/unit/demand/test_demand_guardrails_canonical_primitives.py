from __future__ import annotations

from demand_guardrails.customer_fit_guard import CustomerFitGuard
from demand_guardrails.demand_decision_guard import DemandDecisionGuard
from demand_guardrails.fraud_pattern_guard import FraudPatternGuard
from demand_guardrails.no_monopoly_guard import NoMonopolyGuard
from demand_guardrails.rollback_guard import RollbackGuard
from demand_guardrails.routing_risk_guard import RoutingRiskGuard
from pathlib import Path
from types import SimpleNamespace


class _LiveState:
    def __init__(self, *, risk_score: float, reputation_score: float, capacity_score: float, response_speed_score: float):
        self.risk_score = risk_score
        self.reputation_score = reputation_score
        self.capacity_score = capacity_score
        self.response_speed_score = response_speed_score


def test_demand_decision_guard_uses_shared_threshold_primitives() -> None:
    guard = DemandDecisionGuard()
    allowed, reasons = guard.allow(
        live_state=_LiveState(
            risk_score=0.10,
            reputation_score=0.90,
            capacity_score=0.80,
            response_speed_score=0.90,
        )
    )
    assert allowed is True
    assert reasons == ()

    blocked, blocked_reasons = guard.allow(
        live_state=_LiveState(
            risk_score=0.90,
            reputation_score=0.20,
            capacity_score=0.0,
            response_speed_score=0.0,
        )
    )
    assert blocked is False
    assert set(blocked_reasons) == {
        'risk>=0.70',
        'reputation<0.40',
        'load>0.95',
        'no_response>0.35',
    }


def test_other_demand_guards_share_canonical_threshold_behavior() -> None:
    assert FraudPatternGuard().check(0.30) is True
    assert FraudPatternGuard().check(0.90) is False
    assert NoMonopolyGuard().check(0.40) is True
    assert NoMonopolyGuard().check(0.90) is False
    assert RollbackGuard().check(0.80) is True
    assert RollbackGuard().check(0.10) is False


def test_routing_risk_guard_and_customer_fit_guard_preserve_contracts() -> None:
    candidate = SimpleNamespace(rank_score=0.7, blocked=False)
    blocked_candidate = SimpleNamespace(rank_score=0.7, blocked=True)
    assert RoutingRiskGuard().check(candidate) == 0.7
    assert RoutingRiskGuard().check(blocked_candidate) == 0.0
    assert CustomerFitGuard().check(candidate) is True
    assert CustomerFitGuard().check(SimpleNamespace(rank_score=0.1, blocked=False)) is False


def test_retired_internal_demand_guard_modules_do_not_return() -> None:
    for relative_path in (
        'demand_guardrails/high_risk_business_guard.py',
        'demand_guardrails/no_response_guard.py',
        'demand_guardrails/reputation_floor_guard.py',
        'demand_guardrails/max_load_guard.py',
    ):
        assert not Path(relative_path).exists(), relative_path

def test_internal_only_manual_review_gate_removed() -> None:
    assert not Path("demand_guardrails/manual_review_gate.py").exists()

