from core.application.decision_service import DecisionService
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_history import DecisionHistory
from kernel.decision_space import DecisionSpace
from kernel.decision_candidate import DecisionCandidate
from core.constraints.decision import DecisionConstraints
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


def test_decision_event_payload_is_serializable_dict_shape():
    bus = EventBus()
    core = DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), bus), DecisionHistory())
    result, _ = core.issue(
        DecisionSpace([DecisionCandidate('notify_owner', 'internal', 0.7, 10.0, 0.9)]),
        DecisionConstraints(),
    )
    event = bus.events[-1]
    assert event.payload['approved'] is True
    assert event.payload['executable_action']['objective_name'] == 'profit_adjusted_growth'
