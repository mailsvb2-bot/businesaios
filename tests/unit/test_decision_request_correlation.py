from core.application.decision_service import DecisionService
from core.constraints.decision import DecisionConstraints
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_request import DecisionRequest
from kernel.decision_space import DecisionSpace
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus


def test_decision_request_id_flows_into_recommendation_trace() -> None:
    request = DecisionRequest(
        business_id="b1",
        objective="profit_adjusted_growth",
        input_bundle_id="bundle_1",
        request_id="request_fixed",
    )
    service = DecisionService(
        DecisionSelector(),
        DecisionValidator(),
        DecisionPublisher(DecisionAuditLog(), EventBus()),
        DecisionHistory(),
    )

    result, _ = service.select_action(
        DecisionSpace(
            [
                DecisionCandidate(
                    "notify_owner",
                    "internal",
                    1.0,
                    5.0,
                    0.9,
                )
            ]
        ),
        DecisionConstraints(),
        request,
    )

    assert result.trace is not None
    assert result.trace.request_id == "request_fixed"
    assert result.as_dict()["trace"]["request_id"] == "request_fixed"
    assert result.executable_action is None
