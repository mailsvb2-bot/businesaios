from __future__ import annotations

from pathlib import Path

from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_alert_store_sqlite import SqliteQueueAlertSink
from runtime.queue.queue_alerts import QueueAlert


def _alert(code: str) -> QueueAlert:
    return QueueAlert(tenant_id='tenant-1', queue_name='email', code=code, severity='warning', message=code, created_at=normalize_now())


def test_sqlite_alert_store_rotation_keeps_latest_rows(tmp_path: Path) -> None:
    sink = SqliteQueueAlertSink(path=tmp_path / 'alerts.sqlite3')
    sink.publish((_alert('a'), _alert('b'), _alert('c')))
    removed = sink.rotate(max_rows=2)
    assert removed == 1
    rows = sink.snapshot(limit=10)
    assert [row.code for row in rows] == ['b', 'c']
