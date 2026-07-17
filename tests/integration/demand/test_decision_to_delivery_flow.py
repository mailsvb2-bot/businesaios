from __future__ import annotations

from demand_capture.demand_capture_service import DemandCaptureService
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher
from tests.integration.demand._canonical_issuer import (
    build_registered_demand_policy_issuer,
)


class Ranked:
    def __init__(self, business_id, rank_score, blocked=False):
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked
        self.trace = {"match_score": rank_score}
        self.policy_tags = ()


def test_decision_to_delivery_flow():
    request = DemandCaptureService().capture(
        {"text": "service", "channel": "website", "customer_id": "c1"}
    )
    prepared = {
        "request_id": request.request_id,
        "ranked_candidates": (Ranked("biz-1", 0.9),),
        "trace": {},
    }
    bridge = CanonicalDemandDecisionBridge(
        decision_core=build_registered_demand_policy_issuer()
    )

    decision = bridge.issue(
        request=request,
        routing_preparation=prepared,
    )
    outcome = LeadDeliveryDispatcher().dispatch(
        request=request,
        decision=decision,
    )

    assert outcome and outcome.business_id == "biz-1"
