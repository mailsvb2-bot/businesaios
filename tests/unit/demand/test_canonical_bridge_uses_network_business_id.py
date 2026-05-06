from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from core.application.decision_service import DecisionService
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


class Request:
    request_id = 'req-1'
    customer_id = 'customer-123'


class Candidate:
    def __init__(self) -> None:
        self.business_id = 'biz-1'
        self.rank_score = 0.8
        self.trace = {'match_score': 0.7, 'adjusted_score': 0.8}
        self.blocked = False


def test_canonical_bridge_uses_network_identity_for_decision_request() -> None:
    core = DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory())
    bridge = CanonicalDemandDecisionBridge(decision_core=core)
    decision = bridge.issue(
        request=Request(),
        routing_preparation={'request_id': 'req-1', 'ranked_candidates': (Candidate(),), 'trace': {'preferred_channels': {'biz-1': 'crm'}}},
    )
    assert decision.selected_business_id == 'biz-1'
    latest = core._history.latest()
    assert latest is not None
    assert latest.trace.metadata['business_id'] == 'demand_network'
