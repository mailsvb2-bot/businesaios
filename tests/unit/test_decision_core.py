from core.application.decision_service import DecisionService
from core.constraints.decision import DecisionConstraints
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_space import DecisionSpace
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


def test_recommendation_service_selects_best_valid_candidate() -> None:
    service = DecisionService(
        DecisionSelector(),
        DecisionValidator(),
        DecisionPublisher(DecisionAuditLog(), EventBus()),
        DecisionHistory(),
    )

    result, audit = service.select_action(
        DecisionSpace(
            [
                DecisionCandidate(
                    "notify_owner",
                    "internal",
                    0.5,
                    5.0,
                    0.8,
                ),
                DecisionCandidate(
                    "pause_campaign",
                    "ads",
                    0.8,
                    12.0,
                    0.9,
                ),
            ]
        ),
        DecisionConstraints(),
    )

    assert result.approved is True
    assert result.recommended is True
    assert result.candidate is not None
    assert result.candidate.action_type == "pause_campaign"
    assert result.executable_action is None
    assert result.as_dict()["executable"] is False
    assert audit is not None
