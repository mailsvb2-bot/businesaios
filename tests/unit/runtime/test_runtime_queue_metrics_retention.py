from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from runtime.queue.queue_metrics_retention import QueueMetricsRetentionManager, QueueMetricsRetentionPolicy
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_slo import QueueSLOReport


def _report(*, status: str, pending_jobs: int = 0) -> QueueSLOReport:
    return QueueSLOReport(
        tenant_id='tenant-a',
        queue_name='primary',
        ok=status == 'healthy',
        status=status,
        reasons=() if status == 'healthy' else ('pending_jobs_exceeded',),
        pending_jobs=pending_jobs,
        active_claims=0,
        dead_letter_jobs=0,
        janitor_stale_seconds=0,
        leader_stale_seconds=0,
    )


def test_metrics_retention_compacts_and_rotates_samples(tmp_path: Path) -> None:
    store = SqliteQueueMetricsRollupStore(path=tmp_path / 'rollup.sqlite3')
    first = store.record_sample(report=_report(status='healthy', pending_jobs=1)).observed_at
    store.record_sample(report=_report(status='degraded', pending_jobs=12), observed_at=first + timedelta(seconds=20))
    store.record_sample(report=_report(status='critical', pending_jobs=30), observed_at=first + timedelta(seconds=40))
    store.record_sample(report=_report(status='healthy', pending_jobs=2), observed_at=first + timedelta(days=20))

    manager = QueueMetricsRetentionManager(
        store=store,
        policy=QueueMetricsRetentionPolicy(
            compact_after_seconds=60,
            compact_window_seconds=300,
            purge_after_seconds=86400 * 10,
            max_rows=2,
        ),
    )
    report = manager.apply(tenant_id='tenant-a', queue_name='primary', now=first + timedelta(days=21))

    assert report.compacted_samples >= 1
    assert report.removed_samples >= 1
    assert report.purged_rows >= 1
    assert report.retained_rows <= 2
