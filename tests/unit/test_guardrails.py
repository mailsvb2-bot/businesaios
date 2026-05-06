from guardrails.unsafe_budget_jump_guard import UnsafeBudgetJumpGuard


def test_guard_blocks_large_budget_jump():
    guard = UnsafeBudgetJumpGuard(max_delta=0.2)
    ok, code = guard.check({'budget_delta': 0.4})
    assert ok is False
    assert code == 'unsafe_budget_jump'


def test_guard_blocks_large_negative_budget_jump():
    guard = UnsafeBudgetJumpGuard(max_delta=0.2)
    ok, code = guard.check({'budget_delta': -0.4})
    assert ok is False
    assert code == 'unsafe_budget_jump'


def test_guard_can_derive_delta_from_budget_values():
    guard = UnsafeBudgetJumpGuard(max_delta=10.0)
    ok, code = guard.check({'previous_budget': 10.0, 'new_budget': 15.0})
    assert ok is True
    assert code == 'ok'
