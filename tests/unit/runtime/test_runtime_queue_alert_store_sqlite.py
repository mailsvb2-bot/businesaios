from __future__ import annotations

from pathlib import Path

from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_alert_store_sqlite import SqliteQueueAlertSink
from runtime.queue.queue_alerts import QueueAlert


def test_sqlite_queue_alert_sink_persists_alerts(tmp_path: Path) -> None:
    sink = SqliteQueueAlertSink(path=tmp_path / 'alerts.sqlite3')
    now = normalize_now()
    sink.publish(
        (
            QueueAlert(
                tenant_id='tenant-a',
                queue_name='queue-a',
                code='pending_jobs_exceeded',
                severity='error',
                message='pending depth exceeded',
                created_at=now,
            ),
        )
    )

    rows = sink.snapshot()
    assert len(rows) == 1
    assert rows[0].tenant_id == 'tenant-a'
    assert rows[0].queue_name == 'queue-a'
    assert rows[0].code == 'pending_jobs_exceeded'
