from orchestration.closed_loop_growth_orchestrator import ClosedLoopGrowthFlow as FlowClosedLoopGrowthFlow
from orchestration.closed_loop_growth_orchestrator import ClosedLoopGrowthFlow as CanonicalClosedLoopGrowthFlow


class _OpportunityPipeline:
    def run(self, signals: list[dict]) -> list[dict]:
        return [{"signal_count": len(signals), "action_type": "notify_owner"}]


class _DecisionResult:
    def __init__(self) -> None:
        self.approved = True
        self.executable_action = {"action_type": "notify_owner", "payload": {"n": 1}}


class _DecisionPipeline:
    def run(self, candidates: list[dict], constraints: dict | None = None):
        return _DecisionResult(), {"audit": "ok", "candidates": candidates, "constraints": constraints}


class _ExecutionPipeline:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, action: dict) -> dict:
        self.calls.append(action)
        return {"status": "accepted", "action": action}


class _FeedbackPipeline:
    def run(self, execution_result: dict) -> dict:
        return {"feedback_kind": "execution_feedback", "execution_result": dict(execution_result)}


def test_flow_closed_loop_growth_reexports_canonical_orchestrator() -> None:
    assert FlowClosedLoopGrowthFlow is CanonicalClosedLoopGrowthFlow


def test_canonical_closed_loop_growth_orchestrator_preserves_result_shape() -> None:
    result = CanonicalClosedLoopGrowthFlow().run(
        signals=[{"score": 0.9}],
        opportunity_pipeline=_OpportunityPipeline(),
        decision_pipeline=_DecisionPipeline(),
        execution_pipeline=_ExecutionPipeline(),
        feedback_pipeline=_FeedbackPipeline(),
        constraints={"safe": True},
    )

    assert result["decision_result"].approved is True
    assert result["decision_audit"]["audit"] == "ok"
    assert result["execution_result"]["status"] == "accepted"
    assert result["feedback"]["feedback_kind"] == "execution_feedback"
    assert result["strategy_feedback"] == {"strategy_feedback": result["feedback"]}
