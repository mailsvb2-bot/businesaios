from __future__ import annotations

from execution.self_healing_retry import SelfHealingRetryEngine


def test_self_healing_retry_uses_backoff_for_rate_limit() -> None:
    engine = SelfHealingRetryEngine()
    decision = engine.evaluate(action_type="launch_campaign", retry_kind="recoverable", result_error="rate_limit exceeded", feedback={}, attempt_index=1)
    assert decision.should_retry is True
    assert decision.recovery_mode == "backoff_retry"
    assert decision.backoff_seconds > 0
    assert decision.reason == "rate_limit_backoff"


def test_self_healing_retry_does_not_count_plain_success_as_retry_success(tmp_path) -> None:
    from application.learning.retry_learning_store import RetryLearningStore

    store = RetryLearningStore(root_dir=tmp_path / "retry_learning")
    engine = SelfHealingRetryEngine(learning_store=store)

    decision = engine.evaluate(
        action_type="launch_campaign",
        retry_kind="success",
        result_error=None,
        feedback={"tenant_id": "tenant-1"},
        attempt_index=0,
    )

    assert decision.retry_kind == "success"
    snapshot = store.load(tenant_id="tenant-1", action_type="launch_campaign", error_family="unknown")
    assert snapshot.attempts == 1
    assert snapshot.successes_after_retry == 0


def test_self_healing_retry_caps_recent_retry_events_but_preserves_semantics() -> None:
    engine = SelfHealingRetryEngine()
    recent_events = [
        {
            "action_type": "launch_campaign",
            "retry_kind": "recoverable",
            "result_error": "rate_limit exceeded",
            "attempt_index": index + 1,
            "failed": True,
            "capability": "ads.launch",
        }
        for index in range(200)
    ]

    decision = engine.evaluate(
        action_type="launch_campaign",
        retry_kind="recoverable",
        result_error="rate_limit exceeded",
        feedback={"recent_retry_events": recent_events},
        attempt_index=1,
    )

    assert decision.should_retry is True
    assert decision.backoff_seconds >= 30


def test_self_healing_retry_normalizes_unknown_retry_kind_to_non_recoverable() -> None:
    engine = SelfHealingRetryEngine()

    decision = engine.evaluate(
        action_type="launch_campaign",
        retry_kind="weird_external_status",
        result_error="transport timeout",
        feedback={"tenant_id": "tenant-1"},
        attempt_index=1,
    )

    assert decision.retry_kind == "non_recoverable"
    assert decision.should_retry is False
