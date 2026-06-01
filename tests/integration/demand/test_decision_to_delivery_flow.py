from __future__ import annotations

from core.application.decision_service import DecisionService
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from demand_capture.demand_capture_service import DemandCaptureService
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class Ranked:
    def __init__(self, business_id, rank_score, blocked=False):
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked
        self.trace = {'match_score': rank_score}
        self.policy_tags = ()


def test_decision_to_delivery_flow():
    request = DemandCaptureService().capture({"text": "service", "channel": "website", "customer_id": "c1"})
    prepared = {"ranked_candidates": (Ranked("biz-1", 0.9),), "trace": {}}
    bridge = CanonicalDemandDecisionBridge(decision_core=DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory()))
    decision = bridge.issue(request=request, routing_preparation=prepared)
    outcome = LeadDeliveryDispatcher().dispatch(request=request, decision=decision)
    assert outcome and outcome.business_id == "biz-1"
