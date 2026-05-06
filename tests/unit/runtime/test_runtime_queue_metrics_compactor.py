from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from runtime.queue.queue_metrics_compactor import QueueMetricsCompactor
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_slo import QueueSLOReport


def _report(*, observed_status: str, pending_jobs: int = 0) -> QueueSLOReport:
    return QueueSLOReport(
        tenant_id='tenant-a',
        queue_name='primary',
        ok=observed_status == 'healthy',
        status=observed_status,
        reasons=() if observed_status == 'healthy' else ('pending_jobs_exceeded',),
        pending_jobs=pending_jobs,
        active_claims=0,
        dead_letter_jobs=0,
        janitor_stale_seconds=0,
        leader_stale_seconds=0,
    )


def test_queue_metrics_compactor_compacts_old_windows(tmp_path: Path) -> None:
    store = SqliteQueueMetricsRollupStore(path=tmp_path / 'rollup.sqlite3')
    base = store.record_sample(report=_report(observed_status='healthy', pending_jobs=1)).observed_at
    store.record_sample(report=_report(observed_status='degraded', pending_jobs=10), observed_at=base + timedelta(seconds=30))
    store.record_sample(report=_report(observed_status='critical', pending_jobs=20), observed_at=base + timedelta(seconds=40))
    store.record_sample(report=_report(observed_status='healthy', pending_jobs=2), observed_at=base + timedelta(seconds=400))

    compactor = QueueMetricsCompactor(store=store)
    report = compactor.compact(
        tenant_id='tenant-a',
        queue_name='primary',
        older_than=base + timedelta(seconds=300),
        window_seconds=300,
        now=base + timedelta(seconds=500),
    )

    assert report.compacted_samples == 1
    assert report.removed_samples == 2
    windows = store.list_window_summaries(tenant_id='tenant-a', queue_name='primary', window_seconds=300)
    assert len(windows) == 2
    assert windows[0].latest_status == 'critical'
    assert windows[0].max_pending_jobs == 20
