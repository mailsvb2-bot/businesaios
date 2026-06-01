from __future__ import annotations

from types import SimpleNamespace

from application.headless.feedback import SimpleHeadlessFeedbackReader
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from runtime.execution.executor_result import ExecutionResult


def test_headless_feedback_preserves_capability_operator_view_from_action_payload() -> None:
    reader = SimpleHeadlessFeedbackReader.default()
    request = SimpleNamespace(goal='grow', ceo=None, meta={})
    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='d-1', payload={}, action='launch_campaign'))
    action = ExecutableAction(
        action_id='a-1',
        action_type='notify_owner',
        channel='web',
        payload={
            'capability_diagnostics': {'status': 'blocked', 'headline': 'Blocked', 'operator_action': 'review_and_handoff', 'signals': ()},
            'execution_verdict': {'allowed': False, 'operator_required': True},
            'policy_verdict': {'allowed': False, 'reason': 'tenant_capability_policy_denied'},
            'capability_planning': {'allowed': False, 'fallback_used': False, 'reason': 'tenant_capability_policy_denied'},
        },
        decision_id='d-1',
        correlation_id='c-1',
        objective_name='profit_adjusted_growth',
    )
    action_result = ActionResult(action_id='a-1', status='blocked_by_policy', payload=dict(action.payload))
    result = ExecutionResult(ok=False, output={}, error='blocked')

    feedback = reader.read(
        request=request,
        state=None,
        envelope=envelope,
        executable_action=action,
        action_result=action_result,
        result=result,
        step_index=0,
    )

    assert feedback['capability_diagnostics']['status'] == 'blocked'
    assert feedback['execution_verdict']['operator_required'] is True
    assert feedback['policy_verdict']['allowed'] is False
    assert feedback['capability_view']['diagnostics']['headline'] == 'Blocked'
