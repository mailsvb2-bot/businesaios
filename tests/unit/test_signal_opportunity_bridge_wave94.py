from orchestration.signal_opportunity_bridge import SignalToOpportunityFlow as FlowSignalToOpportunityFlow
from orchestration.signal_opportunity_bridge import SignalToOpportunityFlow as CanonicalSignalToOpportunityFlow
from orchestration.opportunity_decision_bridge import OpportunityToDecisionFlow as FlowOpportunityToDecisionFlow
from orchestration.opportunity_decision_bridge import OpportunityToDecisionFlow as CanonicalOpportunityToDecisionFlow
from orchestration.strategy_feedback_bridge import FeedbackToStrategyFlow as FlowFeedbackToStrategyFlow
from orchestration.strategy_feedback_bridge import FeedbackToStrategyFlow as CanonicalFeedbackToStrategyFlow


class _OpportunityPipeline:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def run(self, signals: list[dict]) -> list[dict]:
        self.calls.append(list(signals))
        return [{"score": len(signals), "action_type": "notify_owner"}]


class _DecisionPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[list[object], dict | None]] = []

    def run(self, candidates: list[object], constraints: dict | None = None):
        self.calls.append((list(candidates), constraints))
        return {"approved": True, "count": len(candidates)}, {"audit": "ok", "constraints": constraints}


def test_flow_signal_to_opportunity_reexports_canonical_bridge() -> None:
    assert FlowSignalToOpportunityFlow is CanonicalSignalToOpportunityFlow


def test_canonical_signal_to_opportunity_bridge_preserves_pipeline_delegation() -> None:
    pipeline = _OpportunityPipeline()
    result = CanonicalSignalToOpportunityFlow().run([{"score": 0.8}, {"score": 0.9}], pipeline)

    assert pipeline.calls == [[{"score": 0.8}, {"score": 0.9}]]
    assert result == [{"score": 2, "action_type": "notify_owner"}]


def test_flow_opportunity_to_decision_reexports_canonical_bridge() -> None:
    assert FlowOpportunityToDecisionFlow is CanonicalOpportunityToDecisionFlow


def test_canonical_opportunity_to_decision_bridge_preserves_constraints_delegation() -> None:
    pipeline = _DecisionPipeline()
    result, audit = CanonicalOpportunityToDecisionFlow().run(
        [{"score": 1.0}],
        pipeline,
        {"safe": True},
    )

    assert pipeline.calls == [([{"score": 1.0}], {"safe": True})]
    assert result == {"approved": True, "count": 1}
    assert audit == {"audit": "ok", "constraints": {"safe": True}}


def test_flow_feedback_to_strategy_reexports_canonical_bridge() -> None:
    assert FlowFeedbackToStrategyFlow is CanonicalFeedbackToStrategyFlow


def test_canonical_feedback_to_strategy_bridge_preserves_result_shape() -> None:
    feedback = {"status": "accepted", "revenue": 42}
    assert CanonicalFeedbackToStrategyFlow().run(feedback) == {"strategy_feedback": feedback}
