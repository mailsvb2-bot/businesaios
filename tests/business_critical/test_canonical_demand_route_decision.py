from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.actions.catalog import build_catalog
from core.actions.names import ACTION_ROUTE_LEAD_V1
from core.ai import reset_decision_core_singleton, set_decision_core_singleton
from core.policies.demand_route_policy import DemandRoutePolicyV1
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from kernel.world_state import WorldStateV1
from runtime.handlers.demand_route import handle_route_lead


@pytest.fixture(autouse=True)
def _isolated_singleton():
    reset_decision_core_singleton()
    try:
        yield
    finally:
        reset_decision_core_singleton()


def _candidate(
    business_id: str,
    *,
    score: float,
    confidence: float = 1.0,
    risk_score: float = 0.0,
    channel: str = "telegram",
) -> dict:
    return {
        "business_id": business_id,
        "action_type": "route_lead",
        "channel": channel,
        "score": score,
        "expected_value": score,
        "confidence": confidence,
        "reasons": ["demand_route_candidate"],
        "payload": {
            "business_id": business_id,
            "rank_score": score,
            "match_score": score,
            "adjusted_score": score,
            "risk_score": risk_score,
        },
        "candidate_id": f"candidate:{business_id}",
    }


def _state(*candidates: dict) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        user={"customer_id": "customer-1"},
        session={"request_id": "request-1"},
        product={
            "product_id": "demand_network",
            "domain": "demand_routing",
            "product_version": "v1",
            "tenant_id": "tenant-1",
        },
        economy={},
        timestamp_ms=1,
        tenant_id="tenant-1",
        user_id="customer-1",
        meta={
            "purpose": "demand_route",
            "demand_route": {
                "request_id": "request-1",
                "candidates": list(candidates),
                "constraints": {},
                "blocked_candidate_count": 0,
                "manual_review_reason": "no_safe_candidates",
            },
        },
    )


def test_policy_selects_the_best_valid_candidate_inside_decision_core() -> None:
    output = DemandRoutePolicyV1().propose(
        _state(
            _candidate("business-a", score=0.4),
            _candidate("business-b", score=0.9, channel="whatsapp"),
            _candidate("business-c", score=0.6),
        )
    )

    assert output.action == ACTION_ROUTE_LEAD_V1
    assert output.payload["selected_business_id"] == "business-b"
    assert output.payload["delivery_channel"] == "whatsapp"
    assert output.payload["requires_manual_review"] is False
    assert output.payload["runner_up_business_ids"] == [
        "business-a",
        "business-c",
    ]


def test_policy_rejects_unsafe_candidates_and_fails_to_manual_review() -> None:
    output = DemandRoutePolicyV1().propose(
        _state(
            _candidate(
                "low-confidence",
                score=0.9,
                confidence=0.0,
            ),
            _candidate(
                "high-risk",
                score=1.0,
                risk_score=1.0,
            ),
        )
    )

    assert output.action == ACTION_ROUTE_LEAD_V1
    assert output.payload["requires_manual_review"] is True
    assert output.payload["manual_review_reason"] == "no_safe_candidates"
    assert output.payload["candidate_count"] == 0
    assert {
        item["candidate_id"] for item in output.payload["rejections"]
    } == {
        "candidate:low-confidence",
        "candidate:high-risk",
    }


def test_route_action_has_a_closed_schema_and_advisory_handler() -> None:
    schema = build_catalog()[ACTION_ROUTE_LEAD_V1].schema
    assert schema.allow_additional is False
    assert "request_id" in schema.required
    assert "selected_business_id" in schema.optional

    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
        )
    )
    effects = SimpleNamespace()
    payload = {
        "request_id": "request-1",
        "requires_manual_review": False,
        "candidate_count": 1,
        "blocked_candidate_count": 0,
        "runner_up_business_ids": [],
        "rejections": [],
        "selected_business_id": "business-a",
    }
    result = handle_route_lead(payload, effects, env)

    assert result == {
        "status": "advisory",
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "route": payload,
    }


class _PolicyEnvelopeCore:
    def issue(self, state):
        output = DemandRoutePolicyV1().propose(state)
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=output.action,
                payload=output.payload,
                decision_id="signed-demand-decision",
                correlation_id="request-bridge",
            )
        )


class _RoutingCandidate:
    def __init__(self, business_id: str, score: float, channel: str) -> None:
        self.business_id = business_id
        self.rank_score = score
        self.blocked = False
        self.trace = {
            "adjusted_score": score,
            "match_score": score,
            "risk_score": 0.0,
        }
        self.channel = channel


class _Request:
    request_id = "request-bridge"
    customer_id = "customer-bridge"
    tenant_id = "tenant-bridge"


def test_bridge_preserves_public_routing_decision_from_signed_envelope() -> None:
    core = _PolicyEnvelopeCore()
    set_decision_core_singleton(core)
    bridge = CanonicalDemandDecisionBridge(decision_core=core)

    decision = bridge.evaluate(
        request=_Request(),
        routing_preparation={
            "request_id": "request-bridge",
            "ranked_candidates": (
                _RoutingCandidate("business-a", 0.4, "telegram"),
                _RoutingCandidate("business-b", 0.9, "whatsapp"),
            ),
            "requires_manual_review": False,
            "trace": {
                "preferred_channels": {
                    "business-a": "telegram",
                    "business-b": "whatsapp",
                }
            },
        },
    )

    assert decision.request_id == "request-bridge"
    assert decision.selected_business_id == "business-b"
    assert decision.runner_up_business_ids == ("business-a",)
    assert decision.requires_manual_review is False
    assert decision.trace["decision_id"] == "signed-demand-decision"
    assert decision.trace["delivery_channel"] == "whatsapp"
