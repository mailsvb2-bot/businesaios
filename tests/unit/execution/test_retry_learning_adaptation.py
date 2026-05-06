from __future__ import annotations

from application.learning.retry_learning_store import RetryLearningStore
from execution.self_healing_retry import SelfHealingRetryEngine


def test_retry_learning_store_is_used_for_adaptation(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / 'retry_learning')
    engine = SelfHealingRetryEngine(learning_store=store)

    first = engine.evaluate(
        action_type='launch_campaign',
        retry_kind='recoverable',
        result_error='rate_limit exceeded',
        feedback={'tenant_id': 'tenant-1'},
        attempt_index=1,
    )
    second = engine.evaluate(
        action_type='launch_campaign',
        retry_kind='recoverable',
        result_error='rate_limit exceeded',
        feedback={'tenant_id': 'tenant-1'},
        attempt_index=1,
    )

    assert first.should_retry is True
    assert second.backoff_seconds >= first.backoff_seconds
    snapshot = store.load(tenant_id='tenant-1', action_type='launch_campaign', error_family='rate_limit')
    assert snapshot.attempts >= 2
