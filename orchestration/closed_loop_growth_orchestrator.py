from orchestration.signal_opportunity_bridge import SignalToOpportunityFlow
from orchestration.opportunity_decision_bridge import OpportunityToDecisionFlow
from execution.decision_execution_bridge import DecisionToExecutionFlow
from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow
from orchestration.strategy_feedback_bridge import FeedbackToStrategyFlow


class ClosedLoopGrowthFlow:
    def run(
        self,
        signals: list[dict],
        opportunity_pipeline: object,
        decision_pipeline: object,
        execution_pipeline: object,
        feedback_pipeline: object,
        constraints: dict | None = None,
    ) -> dict:
        candidates = SignalToOpportunityFlow().run(signals, opportunity_pipeline)
        decision_result, audit = OpportunityToDecisionFlow().run(candidates, decision_pipeline, constraints)
        execution_result = DecisionToExecutionFlow().run(decision_result, execution_pipeline)
        feedback = ExecutionToFeedbackFlow().run(execution_result, feedback_pipeline)
        strategy_feedback = FeedbackToStrategyFlow().run(feedback)
        return {
            'decision_result': decision_result,
            'decision_audit': audit,
            'execution_result': execution_result,
            'feedback': feedback,
            'strategy_feedback': strategy_feedback,
        }
