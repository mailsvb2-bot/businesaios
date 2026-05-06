from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_backend_clock_policy import ensure_aware, utc_now
from tenancy.tenant_metrics_contract import TenantMetricPoint, TenantMetricsStoreContract, normalize_labels


CANON_TENANT_METRICS_EVENT_LOG = True


def _normalize_segment(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text.replace(' ', '_').replace('/', '_').replace(':', '_')


@dataclass(frozen=True)
class TenantMetricsEvent:
    tenant_id: str
    event_name: str
    value: float = 1.0
    emitted_at: datetime = field(default_factory=utc_now)
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _normalize_segment(self.event_name, field_name='event_name')
        if not math.isfinite(float(self.value)):
            raise ValueError('value must be finite')
        ensure_aware(self.emitted_at)
        normalize_labels(self.labels)


class TenantMetricsEventLog:
    def __init__(self, *, store: TenantMetricsStoreContract, namespace: str = 'tenant_runtime') -> None:
        self._store = store
        self._namespace = _normalize_segment(namespace, field_name='namespace')

    def emit(self, event: TenantMetricsEvent) -> TenantMetricPoint:
        event.validate()
        point = TenantMetricPoint(
            tenant_id=event.tenant_id,
            metric_name=f'{self._namespace}.{_normalize_segment(event.event_name, field_name="event_name")}',
            value=float(event.value),
            metric_type='event',
            emitted_at=ensure_aware(event.emitted_at),
            labels=normalize_labels(event.labels),
        )
        return self._store.append(point)

    def emit_counter(
        self,
        *,
        tenant_id: str,
        event_name: str,
        amount: float = 1.0,
        labels: Mapping[str, str] | None = None,
        emitted_at: datetime | None = None,
    ) -> TenantMetricPoint:
        numeric = float(amount)
        if not math.isfinite(numeric):
            raise ValueError('amount must be finite')
        event = TenantMetricsEvent(
            tenant_id=require_tenant_id(tenant_id),
            event_name=_normalize_segment(event_name, field_name='event_name'),
            value=numeric,
            emitted_at=ensure_aware(emitted_at or utc_now()),
            labels=normalize_labels(labels),
        )
        return self.emit(event)


__all__ = ['CANON_TENANT_METRICS_EVENT_LOG', 'TenantMetricsEvent', 'TenantMetricsEventLog']
