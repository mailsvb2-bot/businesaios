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


def test_decision_core_selects_best_valid_candidate():
    core = DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory())
    result, audit = core.issue(
        DecisionSpace([
            DecisionCandidate('notify_owner', 'internal', 0.5, 5.0, 0.8),
            DecisionCandidate('pause_campaign', 'ads', 0.8, 12.0, 0.9),
        ]),
        DecisionConstraints(),
    )
    assert result.approved is True
    assert result.candidate.action_type == 'pause_campaign'
    assert result.executable_action is not None
