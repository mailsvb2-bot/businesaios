from __future__ import annotations

from application.learning.retry_learning_engine import RetryLearningEngine
from application.learning.retry_learning_store import RetryLearningStore


def test_retry_learning_engine_recommends_backoff_and_records_learning(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / 'retry_learning')
    engine = RetryLearningEngine(learning_store=store)

    recommendation = engine.recommend(
        tenant_id='tenant-1',
        business_id='biz-1',
        action_type='launch_campaign',
        retry_kind='recoverable',
        result_error='rate_limit exceeded',
        attempt_index=1,
        feedback={'capability': 'ads.launch'},
        recent_events=[
            {'action_type': 'launch_campaign', 'result_error': 'rate_limit exceeded', 'retry_kind': 'recoverable', 'attempt_index': 1, 'failed': True, 'capability': 'ads.launch'},
            {'action_type': 'launch_campaign', 'result_error': 'rate_limit exceeded', 'retry_kind': 'recoverable', 'attempt_index': 2, 'failed': True, 'capability': 'ads.launch'},
        ],
    )
    assert recommendation.should_retry is True
    assert recommendation.recommended_recovery_mode in {'backoff_retry', 'cooldown_retry'}
    assert recommendation.recommended_backoff_seconds >= 30
    assert recommendation.context.must_not_issue_decision is True

    snapshot = engine.record_outcome(
        tenant_id='tenant-1',
        action_type='launch_campaign',
        retry_kind='recoverable',
        result_error='rate_limit exceeded',
        backoff_seconds=recommendation.recommended_backoff_seconds,
    )
    assert snapshot is not None
    assert snapshot.attempts == 1


def test_retry_learning_engine_stops_on_authorization_errors(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / 'retry_learning')
    engine = RetryLearningEngine(learning_store=store)
    recommendation = engine.recommend(
        tenant_id='tenant-1',
        business_id='biz-1',
        action_type='publish_offer',
        retry_kind='recoverable',
        result_error='authorization failed',
        attempt_index=1,
        feedback={},
        recent_events=[],
    )
    assert recommendation.should_retry is False
    assert recommendation.should_open_operator_handoff is True
    assert recommendation.fallback_action_type == 'notify_owner'


def test_retry_learning_engine_does_not_count_plain_success_as_success_after_retry(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / "retry_learning")
    engine = RetryLearningEngine(learning_store=store)

    snapshot = engine.record_outcome(
        tenant_id="tenant-1",
        action_type="launch_campaign",
        retry_kind="success",
        result_error=None,
        backoff_seconds=0,
        attempt_index=0,
    )

    assert snapshot is not None
    assert snapshot.attempts == 1
    assert snapshot.successes_after_retry == 0


def test_retry_learning_engine_escalates_to_operator_handoff_when_attempt_budget_is_spent(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / "retry_learning")
    engine = RetryLearningEngine(learning_store=store)

    recommendation = engine.recommend(
        tenant_id="tenant-1",
        business_id="biz-1",
        action_type="launch_campaign",
        retry_kind="recoverable",
        result_error="rate_limit exceeded",
        attempt_index=2,
        feedback={"capability": "ads.launch"},
        recent_events=[
            {"action_type": "launch_campaign", "result_error": "rate_limit exceeded", "retry_kind": "recoverable", "attempt_index": 1, "failed": True, "capability": "ads.launch"},
            {"action_type": "launch_campaign", "result_error": "rate_limit exceeded", "retry_kind": "recoverable", "attempt_index": 2, "failed": True, "capability": "ads.launch"},
            {"action_type": "launch_campaign", "result_error": "rate_limit exceeded", "retry_kind": "recoverable", "attempt_index": 3, "failed": True, "capability": "ads.launch", "operator_required": True},
        ],
    )

    assert recommendation.should_retry is False
    assert recommendation.should_open_operator_handoff is True
    assert recommendation.recommended_recovery_mode == "operator_handoff"


def test_retry_learning_engine_uses_cooldown_retry_for_recurring_transport_failures(tmp_path) -> None:
    store = RetryLearningStore(root_dir=tmp_path / "retry_learning")
    engine = RetryLearningEngine(learning_store=store)

    recommendation = engine.recommend(
        tenant_id="tenant-1",
        business_id="biz-1",
        action_type="sync_crm",
        retry_kind="recoverable",
        result_error="transport timeout",
        attempt_index=1,
        feedback={"capability": "crm.sync"},
        recent_events=[
            {"action_type": "sync_crm", "result_error": "transport timeout", "retry_kind": "recoverable", "attempt_index": 1, "failed": True, "capability": "crm.sync"},
            {"action_type": "sync_crm", "result_error": "transport timeout", "retry_kind": "recoverable", "attempt_index": 2, "failed": True, "capability": "crm.sync"},
        ],
    )

    assert recommendation.should_retry is True
    assert recommendation.cooldown_seconds > 0
    assert recommendation.recommended_recovery_mode == "cooldown_retry"
