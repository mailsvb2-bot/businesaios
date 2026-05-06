from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_slo import QueueSLOReport
from runtime.queue.job_contract import normalize_now


def test_queue_metrics_rollup_store_records_and_summarizes_samples(tmp_path: Path) -> None:
    store = SqliteQueueMetricsRollupStore(path=tmp_path / 'queue_rollup.sqlite3')
    now = normalize_now()
    store.record_sample(
        report=QueueSLOReport(
            tenant_id='tenant-a',
            queue_name='queue-a',
            ok=False,
            status='degraded',
            reasons=('pending_jobs_exceeded',),
            pending_jobs=15,
            active_claims=3,
            dead_letter_jobs=0,
            janitor_stale_seconds=1,
            leader_stale_seconds=1,
        ),
        alert_count=1,
        critical_alert_count=0,
        observed_at=now,
    )
    store.record_sample(
        report=QueueSLOReport(
            tenant_id='tenant-a',
            queue_name='queue-a',
            ok=False,
            status='critical',
            reasons=('dead_letter_jobs_exceeded', 'janitor_stale'),
            pending_jobs=7,
            active_claims=2,
            dead_letter_jobs=5,
            janitor_stale_seconds=500,
            leader_stale_seconds=1,
        ),
        alert_count=2,
        critical_alert_count=2,
        observed_at=now + timedelta(seconds=60),
    )

    samples = store.list_samples(tenant_id='tenant-a', queue_name='queue-a')
    assert len(samples) == 2
    summary = store.summarize(tenant_id='tenant-a', queue_name='queue-a')
    assert summary is not None
    assert summary.samples == 2
    assert summary.latest_status == 'critical'
    assert summary.latest_ok is False
    assert summary.max_pending_jobs == 15
    assert summary.max_dead_letter_jobs == 5
    assert summary.total_alert_count == 3
    assert summary.total_critical_alert_count == 2


def test_queue_metrics_rollup_store_can_purge_old_samples(tmp_path: Path) -> None:
    store = SqliteQueueMetricsRollupStore(path=tmp_path / 'queue_rollup.sqlite3')
    now = normalize_now()
    store.record_sample(
        report=QueueSLOReport(
            tenant_id='tenant-a',
            queue_name='queue-a',
            ok=True,
            status='healthy',
            reasons=(),
            pending_jobs=1,
            active_claims=0,
            dead_letter_jobs=0,
            janitor_stale_seconds=1,
            leader_stale_seconds=1,
        ),
        observed_at=now,
    )
    store.record_sample(
        report=QueueSLOReport(
            tenant_id='tenant-a',
            queue_name='queue-a',
            ok=True,
            status='healthy',
            reasons=(),
            pending_jobs=0,
            active_claims=0,
            dead_letter_jobs=0,
            janitor_stale_seconds=1,
            leader_stale_seconds=1,
        ),
        observed_at=now + timedelta(seconds=120),
    )
    removed = store.purge_older_than(older_than=now + timedelta(seconds=60))
    assert removed == 1
    samples = store.list_samples(tenant_id='tenant-a', queue_name='queue-a')
    assert len(samples) == 1
    assert samples[0].pending_jobs == 0
