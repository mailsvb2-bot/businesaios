from core.application.decision_service import DecisionService
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_history import DecisionHistory
from kernel.decision_space import DecisionSpace
from kernel.decision_candidate import DecisionCandidate
from core.constraints.decision import DecisionConstraints
from kernel.decision_request import DecisionRequest
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


def test_decision_request_id_flows_into_action_correlation_id():
    request = DecisionRequest(business_id='b1', objective='profit_adjusted_growth', input_bundle_id='bundle_1', request_id='request_fixed')
    core = DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory())
    result, _ = core.issue(
        DecisionSpace([DecisionCandidate('notify_owner', 'internal', 1.0, 5.0, 0.9)]),
        DecisionConstraints(),
        request,
    )
    assert result.executable_action is not None
    assert result.executable_action.correlation_id == 'request_fixed'
