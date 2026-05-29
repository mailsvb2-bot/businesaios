from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from observability.tenant_metrics_registry import TenantMetricsRegistry

if TYPE_CHECKING:
    from .event_store import SafetyEvent

CANON_SAFETY_METRICS_EXPORT = True


@dataclass(frozen=True)
class SafetyMetricsExporter:
    registry: TenantMetricsRegistry

    def record_event(self, event: SafetyEvent) -> None:
        labels = {
            'action': str(event.action),
            'stage': str(event.stage),
            'status': str(event.status),
            'control': str(event.control or 'none'),
        }
        tid = str(event.tenant_id)
        self.registry.inc(tenant_id=tid, metric_name='safety.events.total', amount=1.0, labels=labels)
        if str(event.status) in {'block', 'review'}:
            self.registry.inc(tenant_id=tid, metric_name='safety.events.interventions', amount=1.0, labels=labels)
        if str(event.status) == 'block':
            self.registry.inc(tenant_id=tid, metric_name='safety.events.blocked', amount=1.0, labels=labels)
            self.registry.inc(
                tenant_id=tid,
                metric_name='safety.incidents.policy_blocks',
                amount=1.0,
                labels={'action': str(event.action), 'control': str(event.control or 'none')},
            )
        if str(event.status) == 'review':
            self.registry.inc(tenant_id=tid, metric_name='safety.events.reviewed', amount=1.0, labels=labels)
        if str(event.stage) == 'approval':
            self.registry.inc(tenant_id=tid, metric_name='safety.approval.events', amount=1.0, labels=labels)
        if str(event.stage) == 'rollback_verify' and str(event.status) == 'failure':
            self.registry.inc(tenant_id=tid, metric_name='safety.rollback.drift', amount=1.0, labels={'action': str(event.action)})
        if str(event.stage) == 'outcome':
            value = 1.0 if str(event.status) == 'success' else 0.0
            self.registry.record_success_rate(
                tenant_id=tid,
                metric_name='safety.execution.success_ratio',
                success_ratio=value,
                labels={'action': str(event.action)},
            )
            self.registry.record_error_rate(
                tenant_id=tid,
                metric_name='safety.execution.failure_ratio',
                error_ratio=0.0 if str(event.status) == 'success' else 1.0,
                labels={'action': str(event.action)},
            )
