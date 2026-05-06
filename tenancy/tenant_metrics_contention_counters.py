from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_metrics_event_log import TenantMetricsEventLog


CANON_TENANT_METRICS_CONTENTION_COUNTERS = True


@dataclass(frozen=True)
class TenantContentionCounterSet:
    lock_contention_metric: str = 'lock_contention'
    retry_metric: str = 'backend_retry'
    timeout_metric: str = 'backend_timeout'
    reconcile_metric: str = 'reconcile_action'


class TenantMetricsContentionCounters:
    def __init__(self, *, event_log: TenantMetricsEventLog, metric_names: TenantContentionCounterSet | None = None) -> None:
        self._event_log = event_log
        self._metric_names = metric_names or TenantContentionCounterSet()

    def record_lock_contention(self, *, tenant_id: str, subsystem: str, labels: Mapping[str, str] | None = None) -> None:
        self._emit(tenant_id=tenant_id, event_name=self._metric_names.lock_contention_metric, labels=self._merge(subsystem=subsystem, labels=labels))

    def record_retry(self, *, tenant_id: str, subsystem: str, attempt: int, labels: Mapping[str, str] | None = None) -> None:
        if int(attempt) <= 0:
            raise ValueError('attempt must be > 0')
        merged = self._merge(subsystem=subsystem, labels=labels)
        merged['attempt'] = str(int(attempt))
        self._emit(tenant_id=tenant_id, event_name=self._metric_names.retry_metric, labels=merged)

    def record_timeout(self, *, tenant_id: str, subsystem: str, operation: str, labels: Mapping[str, str] | None = None) -> None:
        merged = self._merge(subsystem=subsystem, labels=labels)
        op = str(operation or '').strip()
        if not op:
            raise ValueError('operation is required')
        merged['operation'] = op
        self._emit(tenant_id=tenant_id, event_name=self._metric_names.timeout_metric, labels=merged)

    def record_reconcile_action(self, *, tenant_id: str, subsystem: str, action: str, labels: Mapping[str, str] | None = None) -> None:
        merged = self._merge(subsystem=subsystem, labels=labels)
        action_name = str(action or '').strip()
        if not action_name:
            raise ValueError('action is required')
        merged['action'] = action_name
        self._emit(tenant_id=tenant_id, event_name=self._metric_names.reconcile_metric, labels=merged)

    def _emit(self, *, tenant_id: str, event_name: str, labels: Mapping[str, str]) -> None:
        self._event_log.emit_counter(tenant_id=require_tenant_id(tenant_id), event_name=event_name, amount=1.0, labels=labels)

    @staticmethod
    def _merge(*, subsystem: str, labels: Mapping[str, str] | None) -> dict[str, str]:
        value = str(subsystem or '').strip()
        if not value:
            raise ValueError('subsystem is required')
        merged = dict(labels or {})
        merged['subsystem'] = value
        return {str(k).strip(): str(v).strip() for k, v in merged.items() if str(k).strip() and str(v).strip()}


__all__ = [
    'CANON_TENANT_METRICS_CONTENTION_COUNTERS',
    'TenantContentionCounterSet',
    'TenantMetricsContentionCounters',
]
