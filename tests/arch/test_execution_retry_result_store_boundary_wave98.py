from pathlib import Path


def test_action_result_store_is_thin_reexport() -> None:
    content = Path('execution/action_result_store.py').read_text(encoding='utf-8')
    assert 'from execution.run_result_store import ActionResultStore' in content


def test_action_retry_is_thin_reexport_to_execution_owned_policy() -> None:
    content = Path('execution/action_retry.py').read_text(encoding='utf-8')
    assert 'from execution.run_retry_policy import ActionRetry' in content


def test_canonical_action_retry_uses_execution_primitive_retryable_status_set() -> None:
    content = Path('execution/run_retry_policy.py').read_text(encoding='utf-8')
    assert 'from execution.primitives import RetryableStatusSet' in content
    assert 'temporary_failure' in content
