from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from core.policies.demand_route_policy import DemandRoutePolicyV1
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


class _PolicyEnvelopeCore:
    def __init__(self) -> None:
        self.states: list[object] = []

    def issue(self, state):
        self.states.append(state)
        proposed = DemandRoutePolicyV1().propose(state)
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=proposed.action,
                payload=proposed.payload,
                decision_id="signed-demand-route",
                correlation_id="req-1",
            )
        )


class Request:
    request_id = "req-1"
    customer_id = "customer-123"


class Candidate:
    def __init__(self) -> None:
        self.business_id = "biz-1"
        self.rank_score = 0.8
        self.trace = {"match_score": 0.7, "adjusted_score": 0.8}
        self.blocked = False


def test_canonical_bridge_uses_network_identity_for_decision_request() -> None:
    core = _PolicyEnvelopeCore()
    set_decision_core_singleton(core)
    bridge = CanonicalDemandDecisionBridge(decision_core=core)

    decision = bridge.issue(
        request=Request(),
        routing_preparation={
            "request_id": "req-1",
            "ranked_candidates": (Candidate(),),
            "trace": {"preferred_channels": {"biz-1": "crm"}},
        },
    )

    assert decision.selected_business_id == "biz-1"
    assert decision.trace["decision_id"] == "signed-demand-route"
    assert len(core.states) == 1
    state = core.states[0]
    assert state.product["product_id"] == "demand_network"
    assert state.product["domain"] == "demand_routing"
