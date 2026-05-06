from contracts.action_result import ActionResult
from execution.decision_execution_bridge import DecisionToExecutionFlow as CanonicalDecisionToExecutionFlow
from execution.decision_execution_bridge import DecisionToExecutionFlow as FlowDecisionToExecutionFlow
from core.contracts.decision_result import DecisionResult
from core.contracts.decision_trace import DecisionTrace


class _StubExecutionPipeline:
    def __init__(self) -> None:
        self.seen = []

    def run(self, action):
        self.seen.append(action)
        return ActionResult(action_id='a-1', status='accepted', payload={'seen': action})


def test_flow_decision_to_execution_flow_reexports_canonical_bridge() -> None:
    assert FlowDecisionToExecutionFlow is CanonicalDecisionToExecutionFlow


def test_canonical_bridge_returns_skipped_result_when_no_action_exists() -> None:
    bridge = CanonicalDecisionToExecutionFlow()
    decision_result = DecisionResult(
        candidate=None,
        trace=DecisionTrace(request_id='r-1', decision_id='decision_123', steps=[], metadata={}),
        executable_action=None,
    )

    result = bridge.run(decision_result, _StubExecutionPipeline())

    assert result.action_id == 'action_123'
    assert result.status == 'skipped'
    assert result.message == 'no_executable_action'
    assert result.payload == {'approved': False}


def test_canonical_bridge_delegates_to_execution_pipeline_when_action_exists() -> None:
    bridge = CanonicalDecisionToExecutionFlow()
    pipeline = _StubExecutionPipeline()
    action = {'action_id': 'a-1', 'kind': 'notify'}
    decision_result = DecisionResult(candidate=None, executable_action=action)

    result = bridge.run(decision_result, pipeline)

    assert result.status == 'accepted'
    assert pipeline.seen == [action]
