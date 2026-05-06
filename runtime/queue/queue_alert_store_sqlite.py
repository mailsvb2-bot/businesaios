from __future__ import annotations

"""Durable SQLite queue alert sink.

This persists operational alerts only. It must not mutate queue execution state
or become an alternate decision surface.
"""

import importlib
from datetime import datetime
from pathlib import Path
import os
sqlite3 = importlib.import_module("sqlite3")
from threading import RLock

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_alerts import QueueAlert, QueueAlertSink


CANON_RUNTIME_QUEUE_ALERT_STORE_SQLITE = True


def runtime_queue_alert_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_QUEUE_ALERT_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'queue_alerts.sqlite3'


class SqliteQueueAlertSink(QueueAlertSink):
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path) if path is not None else runtime_queue_alert_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = RLock()
        self._closed = False
        self._init_schema()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                with self._connect() as db:
                    db.execute('PRAGMA wal_checkpoint(TRUNCATE);')
            except Exception:
                pass

    def publish(self, alerts: tuple[QueueAlert, ...]) -> None:
        if not alerts:
            return
        self._ensure_open()
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            for alert in alerts:
                db.execute(
                    """
                    INSERT INTO runtime_queue_alerts (
                        tenant_id,
                        queue_name,
                        code,
                        severity,
                        message,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(alert.tenant_id).strip(),
                        str(alert.queue_name).strip(),
                        str(alert.code).strip(),
                        str(alert.severity).strip() or 'warning',
                        str(alert.message),
                        normalize_now(alert.created_at).isoformat(),
                    ),
                )
            db.commit()


    def purge_older_than(self, *, older_than: datetime) -> int:
        self._ensure_open()
        cutoff = normalize_now(older_than).isoformat()
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            removed = db.execute('DELETE FROM runtime_queue_alerts WHERE created_at < ?', (cutoff,)).rowcount
            db.commit()
        return int(removed or 0)

    def rotate(self, *, max_rows: int) -> int:
        self._ensure_open()
        keep = max(0, int(max_rows))
        with self._lock, self._connect() as db:
            row = db.execute('SELECT COUNT(*) AS c FROM runtime_queue_alerts').fetchone()
            count = int(row['c']) if row is not None else 0
            if count <= keep:
                return 0
            remove_count = count - keep
            db.execute('BEGIN IMMEDIATE;')
            removed = db.execute(
                'DELETE FROM runtime_queue_alerts WHERE id IN (SELECT id FROM runtime_queue_alerts ORDER BY id ASC LIMIT ?)',
                (remove_count,),
            ).rowcount
            db.commit()
        return int(removed or 0)

    def snapshot(self, *, limit: int = 1000) -> tuple[QueueAlert, ...]:
        self._ensure_open()
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT tenant_id, queue_name, code, severity, message, created_at
                FROM runtime_queue_alerts
                ORDER BY id ASC
                LIMIT ?
                """,
                (max(0, int(limit)),),
            ).fetchall()
            return tuple(
                QueueAlert(
                    tenant_id=str(row['tenant_id']),
                    queue_name=str(row['queue_name']),
                    code=str(row['code']),
                    severity=str(row['severity']),
                    message=str(row['message']),
                    created_at=normalize_now(datetime.fromisoformat(str(row['created_at']))),
                )
                for row in rows
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=max(0.1, self._busy_timeout_ms / 1000.0), check_same_thread=False)
        db.row_factory = sqlite3.Row
        configure_sqlite(db, prod=is_prod_env())
        db.execute(f'PRAGMA busy_timeout={self._busy_timeout_ms};')
        return db

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_queue_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_alerts_lookup
                    ON runtime_queue_alerts (tenant_id, queue_name, code, created_at);
                """
            )
            db.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('SqliteQueueAlertSink is closed')


__all__ = [
    'CANON_RUNTIME_QUEUE_ALERT_STORE_SQLITE',
    'SqliteQueueAlertSink',
    'runtime_queue_alert_store_path',
]