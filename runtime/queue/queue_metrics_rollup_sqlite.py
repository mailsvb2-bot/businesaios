from __future__ import annotations

"""Durable rollups for queue operational health.

This module persists sampled queue-health facts only:
- SLO verdicts
- queue depth / active claims / dead-letter pressure
- derived alert counts

It must never mutate queue execution state or become a second decision path.
"""

import importlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

sqlite3 = importlib.import_module("sqlite3")
from threading import RLock

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_slo import QueueSLOReport

CANON_RUNTIME_QUEUE_METRICS_ROLLUP_SQLITE = True


def runtime_queue_metrics_rollup_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_QUEUE_METRICS_ROLLUP_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'queue_metrics_rollup.sqlite3'


@dataclass(frozen=True)
class QueueHealthRollup:
    tenant_id: str
    queue_name: str
    status: str
    ok: bool
    pending_jobs: int
    active_claims: int
    dead_letter_jobs: int
    alert_count: int
    critical_alert_count: int
    observed_at: datetime


@dataclass(frozen=True)
class QueueHealthSummary:
    tenant_id: str
    queue_name: str
    samples: int
    latest_status: str
    latest_ok: bool
    max_pending_jobs: int
    max_active_claims: int
    max_dead_letter_jobs: int
    total_alert_count: int
    total_critical_alert_count: int
    first_observed_at: datetime
    last_observed_at: datetime




@dataclass(frozen=True)
class QueueHealthWindowSummary:
    tenant_id: str
    queue_name: str
    window_start: datetime
    window_end: datetime
    samples: int
    latest_status: str
    latest_ok: bool
    max_pending_jobs: int
    max_active_claims: int
    max_dead_letter_jobs: int
    total_alert_count: int
    total_critical_alert_count: int

class SqliteQueueMetricsRollupStore:
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path) if path is not None else runtime_queue_metrics_rollup_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = RLock()
        self._closed = False
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def record_sample(
        self,
        *,
        report: QueueSLOReport,
        alert_count: int = 0,
        critical_alert_count: int = 0,
        observed_at: datetime | None = None,
    ) -> QueueHealthRollup:
        self._ensure_open()
        moment = normalize_now(observed_at)
        rollup = QueueHealthRollup(
            tenant_id=str(report.tenant_id).strip(),
            queue_name=str(report.queue_name).strip(),
            status=str(report.status).strip() or 'unknown',
            ok=bool(report.ok),
            pending_jobs=int(report.pending_jobs),
            active_claims=int(report.active_claims),
            dead_letter_jobs=int(report.dead_letter_jobs),
            alert_count=max(0, int(alert_count)),
            critical_alert_count=max(0, int(critical_alert_count)),
            observed_at=moment,
        )
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                """
                INSERT INTO runtime_queue_health_rollup (
                    tenant_id,
                    queue_name,
                    status,
                    ok,
                    pending_jobs,
                    active_claims,
                    dead_letter_jobs,
                    alert_count,
                    critical_alert_count,
                    observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rollup.tenant_id,
                    rollup.queue_name,
                    rollup.status,
                    1 if rollup.ok else 0,
                    rollup.pending_jobs,
                    rollup.active_claims,
                    rollup.dead_letter_jobs,
                    rollup.alert_count,
                    rollup.critical_alert_count,
                    rollup.observed_at.isoformat(),
                ),
            )
            db.commit()
        return rollup

    def list_samples(self, *, tenant_id: str | None = None, queue_name: str | None = None, limit: int = 1000) -> tuple[QueueHealthRollup, ...]:
        self._ensure_open()
        sql = (
            'SELECT tenant_id, queue_name, status, ok, pending_jobs, active_claims, '
            'dead_letter_jobs, alert_count, critical_alert_count, observed_at '
            'FROM runtime_queue_health_rollup'
        )
        filters: list[str] = []
        args: list[object] = []
        if tenant_id is not None:
            filters.append('tenant_id = ?')
            args.append(str(tenant_id).strip())
        if queue_name is not None:
            filters.append('queue_name = ?')
            args.append(str(queue_name).strip())
        if filters:
            sql += ' WHERE ' + ' AND '.join(filters)
        sql += ' ORDER BY id ASC LIMIT ?'
        args.append(max(0, int(limit)))
        with self._lock, self._connect() as db:
            rows = db.execute(sql, tuple(args)).fetchall()
        return tuple(self._row_to_rollup(row) for row in rows)

    def list_window_summaries(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        window_seconds: int = 300,
        limit: int = 100,
    ) -> tuple[QueueHealthWindowSummary, ...]:
        self._ensure_open()
        window = max(60, int(window_seconds))
        samples = self.list_samples(tenant_id=str(tenant_id).strip(), queue_name=str(queue_name).strip(), limit=1000000)
        buckets: dict[int, list[QueueHealthRollup]] = {}
        if not samples:
            return ()
        anchor_epoch = int(samples[0].observed_at.timestamp())
        for sample in samples:
            epoch = int(sample.observed_at.timestamp())
            bucket = ((epoch - anchor_epoch) // window) * window + anchor_epoch
            buckets.setdefault(bucket, []).append(sample)
        summaries: list[QueueHealthWindowSummary] = []
        for bucket in sorted(buckets)[: max(0, int(limit))]:
            rows = buckets[bucket]
            latest = max(rows, key=lambda item: item.observed_at)
            window_start = normalize_now(datetime.fromtimestamp(bucket, tz=latest.observed_at.tzinfo))
            window_end = window_start + timedelta(seconds=window)
            summaries.append(
                QueueHealthWindowSummary(
                    tenant_id=str(tenant_id).strip(),
                    queue_name=str(queue_name).strip(),
                    window_start=window_start,
                    window_end=window_end,
                    samples=len(rows),
                    latest_status=latest.status,
                    latest_ok=latest.ok,
                    max_pending_jobs=max(item.pending_jobs for item in rows),
                    max_active_claims=max(item.active_claims for item in rows),
                    max_dead_letter_jobs=max(item.dead_letter_jobs for item in rows),
                    total_alert_count=sum(item.alert_count for item in rows),
                    total_critical_alert_count=sum(item.critical_alert_count for item in rows),
                )
            )
        return tuple(summaries)

    def compact_older_than(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        older_than: datetime,
        window_seconds: int = 300,
        now: datetime | None = None,
    ):
        self._ensure_open()
        moment = normalize_now(now)
        cutoff = normalize_now(older_than)
        windows = self.list_window_summaries(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            window_seconds=window_seconds,
            limit=100000,
        )
        source_samples = 0
        compacted_samples = 0
        removed_samples = 0
        from runtime.queue.queue_metrics_compactor import QueueMetricsCompactionReport
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            for window in windows:
                if window.window_end >= cutoff:
                    continue
                source_samples += int(window.samples)
                if window.samples <= 1:
                    continue
                replacement_time = window.window_end - timedelta(seconds=1)
                db.execute(
                    """
                    DELETE FROM runtime_queue_health_rollup
                    WHERE tenant_id = ? AND queue_name = ? AND observed_at >= ? AND observed_at < ?
                    """,
                    (window.tenant_id, window.queue_name, window.window_start.isoformat(), window.window_end.isoformat()),
                )
                db.execute(
                    """
                    INSERT INTO runtime_queue_health_rollup (
                        tenant_id, queue_name, status, ok, pending_jobs, active_claims, dead_letter_jobs,
                        alert_count, critical_alert_count, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        window.tenant_id,
                        window.queue_name,
                        window.latest_status,
                        1 if window.latest_ok else 0,
                        window.max_pending_jobs,
                        window.max_active_claims,
                        window.max_dead_letter_jobs,
                        window.total_alert_count,
                        window.total_critical_alert_count,
                        replacement_time.isoformat(),
                    ),
                )
                compacted_samples += 1
                removed_samples += max(0, int(window.samples) - 1)
            db.commit()
        return QueueMetricsCompactionReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            source_samples=source_samples,
            removed_samples=removed_samples,
            compacted_samples=compacted_samples,
            window_seconds=max(60, int(window_seconds)),
            compacted_at=moment,
        )

    def summarize(self, *, tenant_id: str, queue_name: str) -> QueueHealthSummary | None:
        self._ensure_open()
        with self._lock, self._connect() as db:
            row = db.execute(
                """
                SELECT
                    COUNT(*) AS samples,
                    MAX(pending_jobs) AS max_pending_jobs,
                    MAX(active_claims) AS max_active_claims,
                    MAX(dead_letter_jobs) AS max_dead_letter_jobs,
                    COALESCE(SUM(alert_count), 0) AS total_alert_count,
                    COALESCE(SUM(critical_alert_count), 0) AS total_critical_alert_count,
                    MIN(observed_at) AS first_observed_at,
                    MAX(observed_at) AS last_observed_at
                FROM runtime_queue_health_rollup
                WHERE tenant_id = ? AND queue_name = ?
                """,
                (str(tenant_id).strip(), str(queue_name).strip()),
            ).fetchone()
            if row is None or int(row['samples']) <= 0:
                return None
            latest = db.execute(
                """
                SELECT status, ok
                FROM runtime_queue_health_rollup
                WHERE tenant_id = ? AND queue_name = ?
                ORDER BY observed_at DESC, id DESC
                LIMIT 1
                """,
                (str(tenant_id).strip(), str(queue_name).strip()),
            ).fetchone()
            assert latest is not None
        return QueueHealthSummary(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            samples=int(row['samples']),
            latest_status=str(latest['status']),
            latest_ok=bool(latest['ok']),
            max_pending_jobs=int(row['max_pending_jobs']),
            max_active_claims=int(row['max_active_claims']),
            max_dead_letter_jobs=int(row['max_dead_letter_jobs']),
            total_alert_count=int(row['total_alert_count']),
            total_critical_alert_count=int(row['total_critical_alert_count']),
            first_observed_at=normalize_now(datetime.fromisoformat(str(row['first_observed_at']))),
            last_observed_at=normalize_now(datetime.fromisoformat(str(row['last_observed_at']))),
        )

    def purge_older_than(self, *, older_than: datetime) -> int:
        self._ensure_open()
        cutoff = normalize_now(older_than).isoformat()
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            removed = db.execute('DELETE FROM runtime_queue_health_rollup WHERE observed_at < ?', (cutoff,)).rowcount
            db.commit()
        return int(removed or 0)

    def rotate(self, *, max_rows: int) -> int:
        self._ensure_open()
        retain = max(1, int(max_rows))
        with self._lock, self._connect() as db:
            total = db.execute('SELECT COUNT(*) AS total FROM runtime_queue_health_rollup').fetchone()
            current_total = int(total['total']) if total is not None else 0
            excess = max(0, current_total - retain)
            if excess <= 0:
                return 0
            db.execute('BEGIN IMMEDIATE;')
            removed = db.execute(
                """
                DELETE FROM runtime_queue_health_rollup
                WHERE id IN (
                    SELECT id FROM runtime_queue_health_rollup
                    ORDER BY observed_at ASC, id ASC
                    LIMIT ?
                )
                """,
                (excess,),
            ).rowcount
            db.commit()
        return int(removed or 0)

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
                CREATE TABLE IF NOT EXISTS runtime_queue_health_rollup (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    pending_jobs INTEGER NOT NULL,
                    active_claims INTEGER NOT NULL,
                    dead_letter_jobs INTEGER NOT NULL,
                    alert_count INTEGER NOT NULL,
                    critical_alert_count INTEGER NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_health_rollup_lookup
                    ON runtime_queue_health_rollup (tenant_id, queue_name, observed_at);
                """
            )
            db.commit()

    @staticmethod
    def _row_to_rollup(row: sqlite3.Row) -> QueueHealthRollup:
        return QueueHealthRollup(
            tenant_id=str(row['tenant_id']),
            queue_name=str(row['queue_name']),
            status=str(row['status']),
            ok=bool(row['ok']),
            pending_jobs=int(row['pending_jobs']),
            active_claims=int(row['active_claims']),
            dead_letter_jobs=int(row['dead_letter_jobs']),
            alert_count=int(row['alert_count']),
            critical_alert_count=int(row['critical_alert_count']),
            observed_at=normalize_now(datetime.fromisoformat(str(row['observed_at']))),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('SqliteQueueMetricsRollupStore is closed')


__all__ = [
    'CANON_RUNTIME_QUEUE_METRICS_ROLLUP_SQLITE',
    'QueueHealthRollup',
    'QueueHealthSummary',
    'QueueHealthWindowSummary',
    'SqliteQueueMetricsRollupStore',
    'runtime_queue_metrics_rollup_store_path',
]
