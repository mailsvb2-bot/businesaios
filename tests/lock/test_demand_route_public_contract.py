from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.actions.names import ACTION_ROUTE_LEAD_V1
from demand_decision.canonical_decision_bridge import (
    routing_decision_from_signed_envelope,
)


def _envelope(payload: dict, *, decision_id: str = "decision-route"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            action=ACTION_ROUTE_LEAD_V1,
            payload=dict(payload),
            decision_id=decision_id,
            correlation_id="correlation-route",
        )
    )


@pytest.mark.lock
def test_signed_route_preserves_selected_public_contract() -> None:
    decision = routing_decision_from_signed_envelope(
        request_id="request-1",
        envelope=_envelope(
            {
                "idempotency_key": "demand-route:tenant-1:request-1",
                "request_id": "request-1",
                "requires_manual_review": False,
                "candidate_count": 3,
                "eligible_candidate_count": 2,
                "blocked_candidate_count": 1,
                "selected_business_id": "business-b",
                "runner_up_business_ids": [
                    "business-a",
                    "business-c",
                ],
                "rejections": [],
            }
        ),
        trace={"source": "marketplace"},
        preferred_channels={"business-b": "whatsapp"},
        blocked_count=1,
    )

    assert decision.request_id == "request-1"
    assert decision.selected_business_id == "business-b"
    assert decision.runner_up_business_ids == (
        "business-a",
        "business-c",
    )
    assert decision.requires_manual_review is False
    assert decision.trace["source"] == "marketplace"
    assert decision.trace["decision_id"] == "decision-route"
    assert decision.trace["selected_from_candidates"] == 3
    assert decision.trace["blocked_candidate_count"] == 1
    assert decision.trace["delivery_channel"] == "whatsapp"


@pytest.mark.lock
def test_signed_route_preserves_manual_review_public_contract() -> None:
    decision = routing_decision_from_signed_envelope(
        request_id="request-2",
        envelope=_envelope(
            {
                "idempotency_key": "demand-route:tenant-1:request-2",
                "request_id": "request-2",
                "requires_manual_review": True,
                "candidate_count": 2,
                "eligible_candidate_count": 0,
                "blocked_candidate_count": 0,
                "runner_up_business_ids": [],
                "rejections": [
                    {
                        "candidate_id": "candidate-a",
                        "reason": "risk_too_high",
                    }
                ],
                "manual_review_reason": (
                    "decision_core_rejected_all_candidates"
                ),
            },
            decision_id="decision-review",
        ),
    )

    assert decision.request_id == "request-2"
    assert decision.selected_business_id is None
    assert decision.runner_up_business_ids == ()
    assert decision.requires_manual_review is True
    assert decision.trace["decision_id"] == "decision-review"
    assert (
        decision.trace["manual_review_reason"]
        == "decision_core_rejected_all_candidates"
    )


@pytest.mark.lock
def test_route_adapter_rejects_noncanonical_or_unidentified_envelopes() -> None:
    with pytest.raises(RuntimeError, match="demand_route_unexpected_action"):
        routing_decision_from_signed_envelope(
            request_id="request-3",
            envelope=SimpleNamespace(
                decision=SimpleNamespace(
                    action="send_message@v1",
                    payload={},
                    decision_id="decision-wrong",
                )
            ),
        )

    with pytest.raises(
        RuntimeError,
        match="demand_route_envelope_missing_decision_id",
    ):
        routing_decision_from_signed_envelope(
            request_id="request-3",
            envelope=SimpleNamespace(
                decision=SimpleNamespace(
                    action=ACTION_ROUTE_LEAD_V1,
                    payload={},
                    decision_id="",
                )
            ),
        )
