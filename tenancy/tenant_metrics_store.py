from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_metrics_contract import (
    TenantMetricAggregate,
    TenantMetricPoint,
    TenantMetricsStoreContract,
    labels_signature,
    normalize_labels,
    utc_now,
)


CANON_TENANT_METRICS_STORE = True


@dataclass(frozen=True)
class TenantMetricsSnapshot:
    tenant_id: str
    metrics: Mapping[str, TenantMetricAggregate]


class InMemoryTenantMetricsStore(TenantMetricsStoreContract):
    def __init__(self) -> None:
        self._points: list[TenantMetricPoint] = []
        self._lock = RLock()

    def append(self, point: TenantMetricPoint) -> TenantMetricPoint:
        point.validate()
        with self._lock:
            self._points.append(point)
        return point

    def increment(self, *, tenant_id: str, metric_name: str, amount: float = 1.0, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> TenantMetricPoint:
        point = TenantMetricPoint(
            tenant_id=require_tenant_id(tenant_id),
            metric_name=str(metric_name).strip(),
            value=float(amount),
            metric_type='counter',
            emitted_at=emitted_at or utc_now(),
            labels=normalize_labels(labels),
        )
        return self.append(point)

    def list_points(self, *, tenant_id: str, metric_name: str | None = None, since: datetime | None = None) -> tuple[TenantMetricPoint, ...]:
        tid = require_tenant_id(tenant_id)
        if since is not None and (since.tzinfo is None or since.utcoffset() is None):
            raise ValueError('since must be timezone-aware')
        with self._lock:
            items = [item for item in self._points if item.tenant_id == tid]
        if metric_name is not None:
            name = str(metric_name).strip()
            items = [item for item in items if item.metric_name == name]
        if since is not None:
            items = [item for item in items if item.emitted_at >= since]
        return tuple(sorted(items, key=lambda item: (item.emitted_at, item.metric_name, item.series_signature)))

    def aggregate(self, *, tenant_id: str, metric_name: str, since: datetime | None = None) -> TenantMetricAggregate | None:
        items = list(self.list_points(tenant_id=tenant_id, metric_name=metric_name, since=since))
        if not items:
            return None
        last = items[-1]
        metric_types = {str(item.metric_type) for item in items}
        if len(metric_types) != 1:
            raise ValueError(f"mixed metric types for aggregate are forbidden: tenant={tenant_id} metric={metric_name}")
        values = [float(item.value) for item in items]
        signatures = {labels_signature(item.labels) for item in items}
        aggregate = TenantMetricAggregate(
            tenant_id=last.tenant_id,
            metric_name=last.metric_name,
            sample_count=len(items),
            total=float(sum(values)),
            minimum=float(min(values)),
            maximum=float(max(values)),
            last_value=float(last.value),
            last_emitted_at=last.emitted_at,
            labels=dict(last.labels),
            label_series_count=len(signatures),
            labels_collapsed=len(signatures) > 1,
        )
        aggregate.validate()
        return aggregate

    def snapshot(self, *, tenant_id: str, since: datetime | None = None) -> TenantMetricsSnapshot:
        tid = require_tenant_id(tenant_id)
        points = self.list_points(tenant_id=tid, since=since)
        names = sorted({item.metric_name for item in points})
        metrics = {name: self.aggregate(tenant_id=tid, metric_name=name, since=since) for name in names}
        return TenantMetricsSnapshot(tenant_id=tid, metrics={k: v for k, v in metrics.items() if v is not None})


__all__ = [
    'CANON_TENANT_METRICS_STORE',
    'InMemoryTenantMetricsStore',
    'TenantMetricsSnapshot',
]
