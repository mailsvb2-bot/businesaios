from contracts.executable_action import ExecutableAction
from execution.runners.internal.rollback_action import Runner as RollbackRunner
from guardrails.unsafe_budget_jump_guard import UnsafeBudgetJumpGuard


def test_rollback_on_bad_performance_guard_and_runner():
    guard = UnsafeBudgetJumpGuard(max_delta=0.2)
    ok, code = guard.check({'budget_delta': 0.4})
    result = RollbackRunner().run(
        ExecutableAction(
            action_id='rb1',
            action_type='rollback_action',
            channel='internal',
            payload={'reason': code},
            decision_id='decision_1',
            correlation_id='request_1',
        )
    )
    assert ok is False
    assert code == 'unsafe_budget_jump'
    assert result['status'] == 'accepted'
