from execution.execution_pipeline import ExecutionPipeline as CanonicalExecutionPipeline
from orchestration.execution_pipeline import ExecutionPipeline as OrchestrationExecutionPipeline


class _StubDispatcher:
    def __init__(self) -> None:
        self.seen = []

    def dispatch(self, action):
        self.seen.append(action)
        return {"status": "ok", "action": action}


def test_orchestration_execution_pipeline_reexports_canonical_pipeline() -> None:
    assert OrchestrationExecutionPipeline is CanonicalExecutionPipeline


def test_canonical_execution_pipeline_preserves_dispatch_contract() -> None:
    dispatcher = _StubDispatcher()
    pipeline = CanonicalExecutionPipeline(dispatcher)

    result = pipeline.run({"action_id": "a1"})

    assert result == {"status": "ok", "action": {"action_id": "a1"}}
    assert dispatcher.seen == [{"action_id": "a1"}]
