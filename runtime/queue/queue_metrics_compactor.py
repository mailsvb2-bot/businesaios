from __future__ import annotations

"""Windowed compaction for queue health rollups.

This module only aggregates already-recorded operational facts. It does not
change queue execution state and must never become a planning layer.
"""

from datetime import datetime

from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_metrics_contracts import QueueMetricsCompactionReport
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore

CANON_RUNTIME_QUEUE_METRICS_COMPACTOR = True



class QueueMetricsCompactor:
    def __init__(self, *, store: SqliteQueueMetricsRollupStore) -> None:
        self._store = store

    def compact(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        older_than: datetime,
        window_seconds: int = 300,
        now: datetime | None = None,
    ) -> QueueMetricsCompactionReport:
        moment = normalize_now(now)
        cutoff = normalize_now(older_than)
        return self._store.compact_older_than(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            older_than=cutoff,
            window_seconds=max(60, int(window_seconds)),
            now=moment,
        )


__all__ = [
    'CANON_RUNTIME_QUEUE_METRICS_COMPACTOR',
    'QueueMetricsCompactionReport',
    'QueueMetricsCompactor',
]
