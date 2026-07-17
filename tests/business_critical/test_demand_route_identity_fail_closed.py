from __future__ import annotations

import pytest

from core.policies.demand_route_policy import DemandRoutePolicyV1
from kernel.world_state import WorldStateV1


def _state(*, request_id: str, candidates: list[dict]) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        user={"customer_id": "customer-1"},
        session={"request_id": request_id},
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
                "request_id": request_id,
                "candidates": candidates,
                "constraints": {},
                "blocked_candidate_count": 0,
                "manual_review_reason": "no_safe_candidates",
            },
        },
    )


def test_policy_refuses_to_issue_shared_empty_request_id() -> None:
    with pytest.raises(ValueError, match="requires request_id"):
        DemandRoutePolicyV1().propose(
            _state(request_id="", candidates=[])
        )


def test_candidate_without_business_identity_cannot_be_selected() -> None:
    output = DemandRoutePolicyV1().propose(
        _state(
            request_id="request-1",
            candidates=[
                {
                    "candidate_id": "candidate-without-business",
                    "channel": "telegram",
                    "score": 1.0,
                    "expected_value": 1.0,
                    "confidence": 1.0,
                    "payload": {},
                }
            ],
        )
    )

    assert output.payload["requires_manual_review"] is True
    assert output.payload["eligible_candidate_count"] == 0
    assert "selected_business_id" not in output.payload
    assert output.payload["rejections"] == [
        {
            "candidate_id": "candidate-without-business",
            "reason": "business_id_required",
        }
    ]


def test_business_identity_in_payload_remains_backward_compatible() -> None:
    output = DemandRoutePolicyV1().propose(
        _state(
            request_id="request-1",
            candidates=[
                {
                    "candidate_id": "legacy-candidate",
                    "channel": "telegram",
                    "score": 1.0,
                    "expected_value": 1.0,
                    "confidence": 1.0,
                    "payload": {"business_id": "business-a"},
                }
            ],
        )
    )

    assert output.payload["requires_manual_review"] is False
    assert output.payload["selected_business_id"] == "business-a"
    assert output.payload["selected_candidate_id"] == "legacy-candidate"
