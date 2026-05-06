from orchestration.idempotency import Idempotency
from orchestration.retry_policy import RetryPolicy


def test_orchestration_idempotency_preserves_seen_keys_surface() -> None:
    idem = Idempotency()
    assert idem.first_time('abc') is True
    assert idem.first_time('abc') is False
    assert idem.seen_keys == {'abc'}


def test_orchestration_idempotency_honors_preseeded_seen_keys() -> None:
    idem = Idempotency(seen_keys={'existing'})
    assert idem.first_time('existing') is False
    assert idem.first_time('new') is True
    assert idem.seen_keys == {'existing', 'new'}


def test_orchestration_retry_policy_preserves_retryable_statuses() -> None:
    policy = RetryPolicy()
    assert policy.should_retry({'status': 'temporary_failure'}) is True
    assert policy.should_retry({'status': 'rate_limited'}) is True
    assert policy.should_retry({'status': 'ok'}) is False
    assert policy.should_retry({'status': 'permanent_failure'}) is False
