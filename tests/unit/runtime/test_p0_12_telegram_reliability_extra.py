from runtime.platform.telegram_inbox import TelegramInbox, failure_code, is_terminal_failure


def test_inbox_terminal_codes_vs_transient():
    assert is_terminal_failure(RuntimeError("DECISION_BLOCKED:insufficient_budget"))
    assert is_terminal_failure(RuntimeError("idempotency_resolution:rejected_scope_mismatch"))
    assert not is_terminal_failure(RuntimeError("DECISION_BLOCKED:action_safety_gate_error"))
    assert not is_terminal_failure(TimeoutError("unavailable"))
    assert failure_code(RuntimeError("secret private-user-message")) == "RuntimeError"

def test_retry_horizon_longer_than_lease():
    assert TelegramInbox.retry_horizon_s() > 600
