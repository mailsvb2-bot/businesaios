from core.application.decision_service import DecisionService
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_history import DecisionHistory
from core.contracts.decision_space import DecisionSpace
from core.contracts.decision_candidate import DecisionCandidate
from core.constraints.decision import DecisionConstraints
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


def test_narrowing_audit_records_rejections():
    core = DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory())
    result, audit = core.issue(
        DecisionSpace([
            DecisionCandidate('raise_budget', 'ads', 1.0, 10.0, 0.95, payload={'budget_delta': 0.4}),
            DecisionCandidate('notify_owner', 'internal', 0.4, 3.0, 0.9),
        ]),
        DecisionConstraints(),
    )
    assert result.approved is True
    assert any('budget_delta_too_high' in item for item in audit.removed_candidates)
