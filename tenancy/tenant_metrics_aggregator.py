from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tenancy.tenant_metrics_contract import TenantMetricAggregate, TenantMetricsStoreContract


CANON_TENANT_METRICS_AGGREGATOR = True


@dataclass(frozen=True)
class TenantMetricsReport:
    tenant_id: str
    emitted_metrics: tuple[TenantMetricAggregate, ...]
    generated_at: datetime | None


class TenantMetricsAggregator:
    def __init__(self, *, store: TenantMetricsStoreContract) -> None:
        self._store = store

    def report(self, *, tenant_id: str, metric_names: tuple[str, ...] | list[str], since: datetime | None = None) -> TenantMetricsReport:
        names = tuple(str(item).strip() for item in metric_names if str(item).strip())
        aggregates: list[TenantMetricAggregate] = []
        latest: datetime | None = None
        for name in names:
            aggregate = self._store.aggregate(tenant_id=tenant_id, metric_name=name, since=since)
            if aggregate is None:
                continue
            aggregates.append(aggregate)
            if aggregate.last_emitted_at is not None and (latest is None or aggregate.last_emitted_at > latest):
                latest = aggregate.last_emitted_at
        return TenantMetricsReport(tenant_id=tenant_id, emitted_metrics=tuple(aggregates), generated_at=latest)


__all__ = ['CANON_TENANT_METRICS_AGGREGATOR', 'TenantMetricsAggregator', 'TenantMetricsReport']
