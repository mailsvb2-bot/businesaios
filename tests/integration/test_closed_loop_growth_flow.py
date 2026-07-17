from core.application.decision_service import DecisionService
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from execution.action_dispatcher import ActionDispatcher
from execution.action_idempotency import ActionIdempotency
from execution.action_result_store import ActionResultStore
from execution.action_runner import ActionRunner
from execution.action_validator import ActionValidator
from execution.runners.internal.notify_owner import Runner as NotifyOwnerRunner
from growth.core.growth_engine import GrowthEngine
from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus
from orchestration.closed_loop_growth_orchestrator import ClosedLoopGrowthFlow
from orchestration.decision_pipeline import DecisionPipeline
from orchestration.execution_pipeline import ExecutionPipeline
from orchestration.feedback_pipeline import FeedbackPipeline
from orchestration.opportunity_pipeline import OpportunityPipeline
from shared.registry import ActionRunnerRegistry


def test_closed_loop_growth_flow_preserves_recommendation_without_shadow_execution():
    registry = ActionRunnerRegistry()
    registry.register("notify_owner", NotifyOwnerRunner())
    dispatcher = ActionDispatcher(
        ActionValidator(),
        ActionRunner(registry),
        ActionResultStore(),
        ActionAuditLog(),
        ActionIdempotency(),
    )
    recommendation_service = DecisionService(
        DecisionSelector(),
        DecisionValidator(),
        DecisionPublisher(DecisionAuditLog(), EventBus()),
        DecisionHistory(),
    )

    result = ClosedLoopGrowthFlow().run(
        signals=[
            {
                "channel": "internal",
                "score": 0.8,
                "expected_value": 10.0,
                "action_type": "notify_owner",
            }
        ],
        opportunity_pipeline=OpportunityPipeline(GrowthEngine()),
        decision_pipeline=DecisionPipeline(recommendation_service),
        execution_pipeline=ExecutionPipeline(dispatcher),
        feedback_pipeline=FeedbackPipeline(),
    )

    assert result["decision_result"].recommended is True
    assert result["decision_result"].executable_action is None
    assert result["execution_result"].status == "skipped"
    assert result["execution_result"].message == "no_executable_action"
