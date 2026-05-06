from contracts.action_result import ActionResult
from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow as FlowExecutionToFeedbackFlow
from orchestration.execution_feedback_bridge import ExecutionToFeedbackFlow as CanonicalExecutionToFeedbackFlow


class _StubFeedbackPipeline:
    def __init__(self) -> None:
        self.calls: list[ActionResult] = []

    def run(self, execution_result: ActionResult) -> dict:
        self.calls.append(execution_result)
        return {"feedback_kind": "execution_feedback", "execution_result": {"status": execution_result.status}}


def test_flow_execution_to_feedback_reexports_canonical_bridge() -> None:
    assert FlowExecutionToFeedbackFlow is CanonicalExecutionToFeedbackFlow


def test_canonical_execution_feedback_bridge_delegates_to_feedback_pipeline() -> None:
    bridge = CanonicalExecutionToFeedbackFlow()
    pipeline = _StubFeedbackPipeline()
    result = ActionResult(action_id="a1", status="accepted", payload={})

    feedback = bridge.run(result, pipeline)

    assert pipeline.calls == [result]
    assert feedback == {"feedback_kind": "execution_feedback", "execution_result": {"status": "accepted"}}
