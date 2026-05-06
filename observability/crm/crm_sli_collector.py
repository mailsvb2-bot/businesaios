from __future__ import annotations

from observability.crm.crm_metrics import CrmMetrics


class CrmSliCollector:
    def snapshot(self, metrics: CrmMetrics) -> dict[str, int]:
        return dict(metrics.counters)
