from __future__ import annotations

"""Retention and rotation for queue health rollups.

This module manages operational evidence only. It must not mutate queue
execution state or introduce any alternate planning/decision path.
"""

from dataclasses import dataclass
from datetime import datetime

from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_metrics_compactor import QueueMetricsCompactionReport, QueueMetricsCompactor
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore

CANON_RUNTIME_QUEUE_METRICS_RETENTION = True


@dataclass(frozen=True)
class QueueMetricsRetentionPolicy:
    compact_after_seconds: int = 3600
    compact_window_seconds: int = 300
    purge_after_seconds: int = 86400 * 14
    max_rows: int = 100000


@dataclass(frozen=True)
class QueueMetricsRetentionReport:
    tenant_id: str
    queue_name: str
    compacted_samples: int
    removed_samples: int
    purged_rows: int
    rotated_rows: int
    retained_rows: int
    applied_at: datetime


class QueueMetricsRetentionManager:
    def __init__(
        self,
        *,
        store: SqliteQueueMetricsRollupStore,
        policy: QueueMetricsRetentionPolicy | None = None,
    ) -> None:
        self._store = store
        self._policy = policy or QueueMetricsRetentionPolicy()
        self._compactor = QueueMetricsCompactor(store=store)

    def apply(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        now: datetime | None = None,
    ) -> QueueMetricsRetentionReport:
        moment = normalize_now(now)
        compact_cutoff = normalize_now(moment).fromtimestamp(
            int(moment.timestamp()) - max(0, int(self._policy.compact_after_seconds)),
            tz=moment.tzinfo,
        )
        purge_cutoff = normalize_now(moment).fromtimestamp(
            int(moment.timestamp()) - max(0, int(self._policy.purge_after_seconds)),
            tz=moment.tzinfo,
        )
        compaction: QueueMetricsCompactionReport = self._compactor.compact(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            older_than=compact_cutoff,
            window_seconds=max(60, int(self._policy.compact_window_seconds)),
            now=moment,
        )
        purged = self._store.purge_older_than(older_than=purge_cutoff)
        rotated = self._store.rotate(max_rows=max(1, int(self._policy.max_rows)))
        retained = len(self._store.list_samples(limit=max(1, int(self._policy.max_rows))))
        return QueueMetricsRetentionReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            compacted_samples=int(compaction.compacted_samples),
            removed_samples=int(compaction.removed_samples),
            purged_rows=int(purged),
            rotated_rows=int(rotated),
            retained_rows=int(retained),
            applied_at=moment,
        )


__all__ = [
    'CANON_RUNTIME_QUEUE_METRICS_RETENTION',
    'QueueMetricsRetentionManager',
    'QueueMetricsRetentionPolicy',
    'QueueMetricsRetentionReport',
]
