from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

CANON_RUNTIME_QUEUE_METRICS_CONTRACTS = True


@dataclass(frozen=True)
class QueueMetricsCompactionReport:
    tenant_id: str
    queue_name: str
    source_samples: int
    removed_samples: int
    compacted_samples: int
    window_seconds: int
    compacted_at: datetime


__all__ = ["CANON_RUNTIME_QUEUE_METRICS_CONTRACTS", "QueueMetricsCompactionReport"]
