from __future__ import annotations

from types import SimpleNamespace

from application.headless.feedback import SimpleHeadlessFeedbackReader
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from runtime.execution.executor_result import ExecutionResult


def test_headless_feedback_merges_result_output_capability_view_when_action_payload_is_sparse() -> None:
    reader = SimpleHeadlessFeedbackReader.default()
    request = SimpleNamespace(goal='grow', ceo=None, meta={})
    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='d-1', payload={}, action='launch_campaign'))
    action = ExecutableAction(
        action_id='a-1',
        action_type='launch_campaign',
        channel='web',
        payload={'capability_planning': {'allowed': True, 'reason': 'capability_ok'}},
        decision_id='d-1',
        correlation_id='c-1',
        objective_name='profit_adjusted_growth',
    )
    action_result = ActionResult(action_id='a-1', status='completed', payload=dict(action.payload))
    result = ExecutionResult(
        ok=True,
        output={
            'capability_diagnostics': {'status': 'watch', 'headline': 'Evidence cooling.', 'operator_action': 'monitor', 'signals': ({'code': 'stale_evidence', 'severity': 'warning'},)},
            'execution_verdict': {'allowed': True, 'approval_required': False},
            'policy_verdict': {'allowed': True, 'recommended_autonomy_tier': 'bounded_autonomy'},
        },
        error=None,
    )

    feedback = reader.read(request=request, state=None, envelope=envelope, executable_action=action, action_result=action_result, result=result, step_index=0)

    assert feedback['capability_view']['diagnostics']['status'] == 'watch'
    assert feedback['capability_diagnostics']['operator_action'] == 'monitor'
    assert feedback['execution_verdict']['allowed'] is True
    assert feedback['policy_verdict']['recommended_autonomy_tier'] == 'bounded_autonomy'
