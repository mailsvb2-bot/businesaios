from __future__ import annotations

from datetime import UTC, datetime, timedelta

from runtime.business_autonomy.provider_pacing import ProviderPacingCoordinator
from runtime.platform.business_autonomy_sqlite_distributed_state import (
    SQLiteDistributedCompareAndSwap,
    SQLiteStateDatabase,
)
from runtime.queue import InMemoryJobStore, JobDispatchRequest, JobScheduler


def _coordinator(path):
    database = SQLiteStateDatabase(path)
    return ProviderPacingCoordinator(
        SQLiteDistributedCompareAndSwap(database, scope="provider_runtime_pacing")
    )


def test_max_pacing_is_persistent_idempotent_and_business_scoped(tmp_path) -> None:
    now = datetime(2026, 9, 3, 17, 0, 0, tzinfo=UTC)
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    first = coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="chat-1", reservation_id="job-1", now=now,
    )
    replay = _coordinator(tmp_path / "state.sqlite3").reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="chat-1", reservation_id="job-1", now=now,
    )
    same_recipient = coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="chat-1", reservation_id="job-2", now=now,
    )
    other_business = coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-b", provider_key="max_messaging",
        recipient_id="chat-1", reservation_id="job-3", now=now,
    )
    assert first is not None and replay is not None and same_recipient is not None
    assert replay.scheduled_at == first.scheduled_at == now
    assert same_recipient.scheduled_at == now + timedelta(milliseconds=550)
    assert other_business is not None and other_business.scheduled_at == now


def test_max_pacing_applies_connection_spacing_to_distinct_recipients(tmp_path) -> None:
    now = datetime(2026, 9, 3, 17, 0, 0, tzinfo=UTC)
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    first = coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="chat-1", reservation_id="job-1", now=now,
    )
    second = coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="chat-2", reservation_id="job-2", now=now,
    )
    assert first is not None and second is not None
    assert first.scheduled_at == now
    assert second.scheduled_at == now + timedelta(milliseconds=40)


def test_pacing_state_does_not_store_raw_recipient_identity(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    coordinator = _coordinator(path)
    coordinator.reserve(
        tenant_id="tenant-a", business_id="biz-a", provider_key="max_messaging",
        recipient_id="private-user-778899", reservation_id="provider-sync-secret",
        now=datetime(2026, 9, 3, 17, 0, 0, tzinfo=UTC),
    )
    assert b"private-user-778899" not in path.read_bytes()
    assert b"provider-sync-secret" not in path.read_bytes()


def test_job_not_before_preserves_subsecond_pacing_without_consuming_attempt(tmp_path) -> None:
    del tmp_path
    now = datetime(2026, 9, 3, 17, 0, 0, tzinfo=UTC)
    store = InMemoryJobStore()
    request = JobDispatchRequest(
        tenant_id="tenant-a", job_id="paced-job", queue_name="provider_sync",
        job_type="provider_sync.dispatch", payload={"capability": "provider_sync.dispatch"},
        dedupe_key="paced-job", not_before=now + timedelta(milliseconds=550),
    )
    job = request.to_record(now=now)
    store.put(job)
    early = JobScheduler(store=store).select_due_jobs(
        tenant_id="tenant-a", queue_name="provider_sync", now=now + timedelta(milliseconds=549)
    )
    due = JobScheduler(store=store).select_due_jobs(
        tenant_id="tenant-a", queue_name="provider_sync", now=now + timedelta(milliseconds=550)
    )
    assert job.run_at == now + timedelta(milliseconds=550)
    assert early.jobs == ()
    assert tuple(item.job_id for item in due.jobs) == ("paced-job",)
    assert store.get(tenant_id="tenant-a", job_id="paced-job").attempts == 0
