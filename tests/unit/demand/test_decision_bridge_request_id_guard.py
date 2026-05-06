from __future__ import annotations

import pytest

from core.application.decision_service import DecisionService
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


class Request:
    request_id = 'req-1'
    customer_id = 'cust-1'


class Candidate:
    business_id = 'biz-1'
    rank_score = 0.8
    trace = {'match_score': 0.8}
    blocked = False


def test_bridge_rejects_mismatched_request_id() -> None:
    bridge = CanonicalDemandDecisionBridge(
        decision_core=DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory())
    )
    with pytest.raises(ValueError, match='request_id'):
        bridge.issue(
            request=Request(),
            routing_preparation={'request_id': 'other', 'ranked_candidates': (Candidate(),), 'trace': {}},
        )
