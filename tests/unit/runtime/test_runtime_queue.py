from __future__ import annotations

from datetime import timedelta

import pytest

from runtime.queue import (
    BackpressurePolicy,
    DeadLetterRecord,
    InMemoryJobDeadLetterStore,
    InMemoryJobStore,
    JobDispatcher,
    JobDispatchRequest,
    JobLease,
    JobPriority,
    JobRecord,
    JobRetryPolicy,
    JobScheduler,
    JobState,
    JobWorker,
    RateLimitGuard,
    ThrottlePolicy,
)
from runtime.queue.job_contract import MAX_JOB_TAGS, utc_now


def _request(**overrides: object) -> JobDispatchRequest:
    data = {
        "tenant_id": "tenant-1",
        "job_id": "job-1",
        "queue_name": "email",
        "job_type": "send_email",
        "payload": {"recipient": "a@example.com"},
        "dedupe_key": "dedupe-1",
    }
    data.update(overrides)
    return JobDispatchRequest(**data)


def test_job_record_requires_timezone_aware_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        JobRecord(
            tenant_id="tenant-1",
            job_id="job-1",
            queue_name="email",
            job_type="send_email",
            payload={},
            dedupe_key="d1",
            run_at=utc_now().replace(tzinfo=None),
        )


def test_dispatch_request_normalizes_and_validates() -> None:
    request = _request(delay_seconds=-10, tags=(" one ", "two"))
    assert request.delay_seconds == 0
    assert request.tags == ("one", "two")


def test_job_store_supports_redispatch_after_terminal_state_same_dedupe() -> None:
    store = InMemoryJobStore()
    first = store.put(_request().to_record())
    store.mark_dead_letter(tenant_id=first.tenant_id, job_id=first.job_id, error="boom")

    second = store.put(
        _request(job_id="job-2", dedupe_key="dedupe-1").to_record(
            now=utc_now() + timedelta(seconds=1)
        )
    )
    assert second.job_id == "job-2"
    assert store.get_by_dedupe_key(tenant_id="tenant-1", dedupe_key="dedupe-1") == second


def test_scheduler_reclaims_expired_claims() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    job = store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id=job.tenant_id, job_id=job.job_id, owner_id="w1", lease_seconds=1, now=now)
    assert claimed is not None

    batch = JobScheduler(store=store).select_due_jobs(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    assert batch.reclaimed_expired_claims == 1
    assert [item.job_id for item in batch.jobs] == ["job-1"]


def test_worker_treats_dict_failure_as_failure_and_retries() -> None:
    store = InMemoryJobStore()
    dead = InMemoryJobDeadLetterStore()
    now = utc_now()
    store.put(_request(max_attempts=3).to_record(now=now))
    scheduler = JobScheduler(store=store)
    worker = JobWorker(
        worker_id="w1",
        store=store,
        scheduler=scheduler,
        dead_letter_store=dead,
        runner=lambda job: {"ok": False, "status": "temporary_failure", "error": "timeout", "retry_delay_seconds": 7},
    )
    report = worker.tick(tenant_id="tenant-1", queue_name="email", now=now)
    assert report.retried == 1
    current = store.get(tenant_id="tenant-1", job_id="job-1")
    assert current is not None
    assert current.state is JobState.PENDING
    assert current.last_error == "RuntimeError:timeout"


def test_worker_moves_terminal_marker_to_dead_letter() -> None:
    store = InMemoryJobStore()
    dead = InMemoryJobDeadLetterStore()
    now = utc_now()
    store.put(_request(max_attempts=5).to_record(now=now))
    scheduler = JobScheduler(store=store)
    worker = JobWorker(
        worker_id="w1",
        store=store,
        scheduler=scheduler,
        dead_letter_store=dead,
        runner=lambda job: {"ok": False, "status": "error", "error": "NON_RETRYABLE connector schema mismatch"},
    )
    report = worker.tick(tenant_id="tenant-1", queue_name="email", now=now)
    assert report.dead_lettered == 1
    current = store.get(tenant_id="tenant-1", job_id="job-1")
    assert current is not None and current.state is JobState.DEAD_LETTER
    assert dead.get(tenant_id="tenant-1", job_id="job-1") is not None


def test_rate_limit_guard_blocks_after_limit() -> None:
    guard = RateLimitGuard(limit_per_minute=2)
    assert guard.evaluate(tenant_id="tenant-1", queue_name="email").allowed is True
    assert guard.evaluate(tenant_id="tenant-1", queue_name="email").allowed is True
    verdict = guard.evaluate(tenant_id="tenant-1", queue_name="email")
    assert verdict.allowed is False
    assert verdict.retry_after_seconds >= 1


def test_dispatcher_dedupe_returns_existing_pending_job() -> None:
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    first = dispatcher.dispatch(_request())
    second = dispatcher.dispatch(_request(job_id="job-2"))
    assert first.accepted is True
    assert second.reason == "dedupe_existing"
    assert second.job is not None and second.job.job_id == "job-1"


def test_backpressure_uses_claimed_and_pending_depth() -> None:
    policy = BackpressurePolicy(queue_soft_limit=2, queue_hard_limit=4, claimed_soft_limit=1, claimed_hard_limit=2)
    assert policy.evaluate(queue_depth=1, claimed_depth=0).reason == "normal"
    assert policy.evaluate(queue_depth=2, claimed_depth=0).reason == "queue_soft_pressure"
    blocked = policy.evaluate(queue_depth=2, claimed_depth=2)
    assert blocked.allowed is False


def test_throttle_policy_can_return_zero_for_empty_queue() -> None:
    decision = ThrottlePolicy(max_batch_size=10, max_concurrency_hint=4).decide(queue_depth=0, active_claims=0)
    assert decision.max_claim_count == 0
    assert decision.reason == "queue_empty"


def test_job_lease_requires_ordered_times() -> None:
    now = utc_now()
    with pytest.raises(ValueError, match="greater than"):
        JobLease(owner_id="w1", fencing_token=1, claimed_at=now, expires_at=now)


def test_retry_policy_dead_letters_when_attempt_budget_exhausted() -> None:
    job = JobRecord(
        tenant_id="tenant-1",
        job_id="job-1",
        queue_name="email",
        job_type="send_email",
        payload={},
        dedupe_key="d1",
        run_at=utc_now(),
        attempts=3,
        max_attempts=3,
        state=JobState.CLAIMED,
        lease=JobLease(owner_id="w1", fencing_token=1, claimed_at=utc_now(), expires_at=utc_now() + timedelta(seconds=10)),
    )
    decision = JobRetryPolicy().classify(job=job, error=RuntimeError("boom"))
    assert decision.move_to_dead_letter is True
    assert decision.reason == "attempt_budget_exhausted"


def test_job_store_release_claim_requires_same_owner() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=30, now=now)
    assert store.release_claim(tenant_id="tenant-1", job_id="job-1", owner_id="w2", now=now) is None
    released = store.release_claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now)
    assert released is not None and released.state is JobState.PENDING


def test_dispatcher_respects_backpressure_before_store_put() -> None:
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(
        store=store,
        rate_limit_guard=RateLimitGuard(limit_per_minute=100),
        backpressure_policy=BackpressurePolicy(queue_soft_limit=1, queue_hard_limit=1, claimed_soft_limit=1, claimed_hard_limit=1),
    )
    assert dispatcher.dispatch(_request()).accepted is True
    second = dispatcher.dispatch(_request(job_id="job-2", dedupe_key="dedupe-2"))
    assert second.accepted is False
    assert second.reason == "queue_hard_limit_reached"


def test_public_api_surface_imports() -> None:
    from runtime.queue import public_api

    assert public_api.CANON_RUNTIME_QUEUE_PUBLIC_API is True
    assert public_api.JobWorker is JobWorker


def test_dispatch_request_rejects_out_of_range_priority() -> None:
    with pytest.raises(ValueError, match="priority"):
        _request(priority=101)


def test_dispatch_request_rejects_out_of_range_max_attempts() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        _request(max_attempts=0)


def test_dispatch_request_rejects_oversized_payload_early() -> None:
    with pytest.raises(ValueError, match="payload is too large"):
        _request(payload={"blob": "x" * 300_000})


def test_job_result_normalizes_retry_delay_seconds() -> None:
    result = JobWorker(
        worker_id="w1",
        store=InMemoryJobStore(),
        scheduler=JobScheduler(store=InMemoryJobStore()),
        runner=lambda job: None,
    )._normalize_result(
        job=JobRecord(
            tenant_id="tenant-1",
            job_id="job-r",
            queue_name="email",
            job_type="send_email",
            payload={},
            dedupe_key="dr",
            run_at=utc_now(),
        ),
        outcome={"ok": False, "retry_delay_seconds": "5", "error": "boom"},
    )
    assert result.retry_delay_seconds == 5


def test_store_rejects_conflicting_reuse_of_same_job_id() -> None:
    store = InMemoryJobStore()
    store.put(_request().to_record())
    with pytest.raises(ValueError, match="job_id already exists"):
        store.put(_request(payload={"recipient": "b@example.com"}).to_record())


def test_store_rejects_invalid_terminal_transition() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now)
    store.mark_succeeded(tenant_id="tenant-1", job_id="job-1", now=now)
    with pytest.raises(ValueError, match="invalid state transition"):
        store.mark_dead_letter(tenant_id="tenant-1", job_id="job-1", error="boom", now=now)


def test_release_claim_requires_non_empty_owner() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now)
    with pytest.raises(ValueError, match="owner_id"):
        store.release_claim(tenant_id="tenant-1", job_id="job-1", owner_id=" ", now=now)


def test_dead_letter_store_normalizes_error_and_zero_limit() -> None:
    store = InMemoryJobDeadLetterStore()
    store.put(
        DeadLetterRecord(
            tenant_id="tenant-1",
            job_id="job-1",
            queue_name="email",
            job_type="send_email",
            reason="boom",
            last_error="   very bad   ",
        )
    )
    record = store.get(tenant_id="tenant-1", job_id="job-1")
    assert record is not None and record.last_error == "very bad"
    assert store.list_for_queue(tenant_id="tenant-1", queue_name="email", limit=0) == ()


def test_queue_namespace_public_api_alias_is_installed() -> None:
    import runtime.queue as queue_ns

    assert queue_ns.public_api is queue_ns


def test_dispatcher_returns_accepted_reason_for_new_job() -> None:
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    verdict = dispatcher.dispatch(_request())
    assert verdict.reason == "accepted"


def test_runtime_executor_queue_support_accepts_dispatch_and_runs_worker() -> None:
    from runtime.executor import RuntimeExecutor

    class _Guard:
        def execute_once(self, *args, **kwargs):
            return None

    class _Handlers:
        pass

    class _Events:
        def __init__(self):
            self.items = []
        def emit(self, **kwargs):
            self.items.append(kwargs)

    class _PolicyRegistry:
        pass

    store = InMemoryJobStore()
    executor = RuntimeExecutor(
        guard=_Guard(),
        handlers=_Handlers(),
        event_log=_Events(),
        policy_registry=_PolicyRegistry(),
        queue_store=store,
        queue_runner=lambda job: {"ok": True, "status": "done", "output": {"job_type": job.job_type}},
    )
    verdict = executor.enqueue_runtime_job(_request())
    assert verdict.accepted is True
    report = executor.run_queue_tick(tenant_id="tenant-1", queue_name="email")
    assert report.succeeded == 1
    current = store.get(tenant_id="tenant-1", job_id="job-1")
    assert current is not None and current.state is JobState.SUCCEEDED


def test_runtime_executor_queue_support_fails_without_runner_and_dead_letters() -> None:
    from runtime.executor import RuntimeExecutor

    class _Guard:
        def execute_once(self, *args, **kwargs):
            return None

    class _Handlers:
        pass

    class _Events:
        def emit(self, **kwargs):
            return None

    class _PolicyRegistry:
        pass

    store = InMemoryJobStore()
    dead = InMemoryJobDeadLetterStore()
    executor = RuntimeExecutor(
        guard=_Guard(),
        handlers=_Handlers(),
        event_log=_Events(),
        policy_registry=_PolicyRegistry(),
        queue_store=store,
        queue_dead_letter_store=dead,
        queue_retry_policy=JobRetryPolicy(terminal_error_markers=("RUNTIME_QUEUE_RUNNER_NOT_CONFIGURED",)),
    )
    assert executor.enqueue_runtime_job(_request()).accepted is True
    report = executor.run_queue_tick(tenant_id="tenant-1", queue_name="email")
    assert report.dead_lettered == 1
    assert dead.get(tenant_id="tenant-1", job_id="job-1") is not None


def test_dispatch_request_rejects_too_many_tags() -> None:
    with pytest.raises(ValueError, match="too many tags"):
        _request(tags=tuple(f"t{i}" for i in range(MAX_JOB_TAGS + 1)))


def test_job_record_rejects_attempts_above_max_attempts() -> None:
    with pytest.raises(ValueError, match="attempts must be <= max_attempts"):
        JobRecord(
            tenant_id="tenant-1",
            job_id="job-over",
            queue_name="email",
            job_type="send_email",
            payload={},
            dedupe_key="over",
            run_at=utc_now(),
            attempts=2,
            max_attempts=1,
        )


def test_job_store_reschedule_allows_zero_delay_for_immediate_retry() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now)
    updated = store.reschedule(tenant_id="tenant-1", job_id="job-1", delay_seconds=0, error="boom", now=now)
    assert updated.run_at == now


def test_job_store_never_regresses_updated_at_on_clock_skew() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now)
    assert claimed is not None
    renewed = store.renew_lease(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now - timedelta(seconds=5))
    assert renewed is not None
    assert renewed.updated_at >= claimed.updated_at
    released = store.release_claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", now=now - timedelta(seconds=5))
    assert released is not None
    assert released.updated_at >= renewed.updated_at


def test_dead_letter_store_rejects_mismatched_original_job_identity() -> None:
    store = InMemoryJobDeadLetterStore()
    with pytest.raises(ValueError, match="original_job tenant_id"):
        store.put(
            DeadLetterRecord(
                tenant_id="tenant-1",
                job_id="job-1",
                queue_name="email",
                job_type="send_email",
                reason="boom",
                original_job=JobRecord(
                    tenant_id="tenant-2",
                    job_id="job-1",
                    queue_name="email",
                    job_type="send_email",
                    payload={},
                    dedupe_key="x",
                    run_at=utc_now(),
                ),
            )
        )


def test_dead_letter_store_lists_newest_first_and_validates_queue_name() -> None:
    store = InMemoryJobDeadLetterStore()
    first = store.put(
        DeadLetterRecord(
            tenant_id="tenant-1",
            job_id="job-1",
            queue_name="email",
            job_type="send_email",
            reason="boom",
            failed_at=utc_now(),
        )
    )
    second = store.put(
        DeadLetterRecord(
            tenant_id="tenant-1",
            job_id="job-2",
            queue_name="email",
            job_type="send_email",
            reason="boom",
            failed_at=utc_now() + timedelta(seconds=1),
        )
    )
    listed = store.list_for_queue(tenant_id="tenant-1", queue_name="email")
    assert listed[0].job_id == second.job_id and listed[1].job_id == first.job_id
    with pytest.raises(ValueError, match="queue_name"):
        store.list_for_queue(tenant_id="tenant-1", queue_name=" ")


def test_worker_normalizes_mapping_result_and_runtime_executor_emits_tick_event() -> None:
    from runtime.executor import RuntimeExecutor

    class _Guard:
        def execute_once(self, *args, **kwargs):
            return None

    class _Handlers:
        pass

    class _Events:
        def __init__(self):
            self.items = []
        def emit(self, **kwargs):
            self.items.append(kwargs)

    class _PolicyRegistry:
        pass

    class _MappingResult(dict):
        pass

    events = _Events()
    executor = RuntimeExecutor(
        guard=_Guard(),
        handlers=_Handlers(),
        event_log=events,
        policy_registry=_PolicyRegistry(),
        queue_store=InMemoryJobStore(),
        queue_runner=lambda job: _MappingResult(ok=True, status="done", output={"job_type": job.job_type}),
    )
    assert executor._queue_support.rate_limit_guard is not None
    assert executor._queue_support.backpressure_policy is not None
    assert executor._queue_support.throttle_policy is not None
    assert executor._queue_support.retry_policy is not None
    assert executor.enqueue_runtime_job(_request()).accepted is True
    report = executor.run_queue_tick(tenant_id="tenant-1", queue_name="email")
    assert report.succeeded == 1
    assert any(item.get("event_type") == "runtime_queue_worker_tick" for item in events.items)


def test_retry_policy_dead_letters_cancelled_errors() -> None:
    job = JobRecord(
        tenant_id="tenant-1",
        job_id="job-cancelled",
        queue_name="email",
        job_type="send_email",
        payload={},
        dedupe_key="d-cancelled",
        run_at=utc_now(),
        attempts=1,
        max_attempts=3,
        state=JobState.CLAIMED,
        lease=JobLease(owner_id="w1", fencing_token=1, claimed_at=utc_now(), expires_at=utc_now() + timedelta(seconds=10)),
    )

    decision = JobRetryPolicy().classify(job=job, error=RuntimeError("job cancelled by operator"))

    assert decision.should_retry is False
    assert decision.move_to_dead_letter is True
    assert decision.error_family == "cancelled"


def test_retry_policy_rate_limit_uses_family_aware_backoff() -> None:
    job = JobRecord(
        tenant_id="tenant-1",
        job_id="job-rate",
        queue_name="email",
        job_type="send_email",
        payload={},
        dedupe_key="d-rate",
        run_at=utc_now(),
        attempts=1,
        max_attempts=4,
        state=JobState.CLAIMED,
        lease=JobLease(owner_id="w1", fencing_token=1, claimed_at=utc_now(), expires_at=utc_now() + timedelta(seconds=10)),
    )

    decision = JobRetryPolicy(jitter_seconds=0).classify(job=job, error=RuntimeError("429 rate_limit exceeded"))

    assert decision.should_retry is True
    assert decision.move_to_dead_letter is False
    assert decision.error_family == "rate_limit"
    assert decision.delay_seconds >= 30
