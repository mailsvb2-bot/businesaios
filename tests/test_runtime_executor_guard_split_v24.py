from pathlib import Path


def test_executor_uses_split_helpers() -> None:
    text = Path('runtime/executor.py').read_text(encoding='utf-8')
    assert 'runtime.execution.executor_audit' in text
    assert 'runtime.execution.executor_commit' in text
    assert 'runtime.execution.executor_core' in text
    assert 'runtime.execution.executor_recovery' in text


def test_guard_uses_split_helpers() -> None:
    text = Path('runtime/guard.py').read_text(encoding='utf-8')
    assert 'runtime.enforcement.signature_gate' in text
    assert 'runtime.enforcement.idempotency_gate' in text
    assert 'validate_execute_plan_payload' in text
    assert 'validate_telegram_transport_payload' in text
