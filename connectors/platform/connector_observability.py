from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

from observability.action_audit_log import ActionAuditLog, build_default_action_audit_log
from observability.metrics import InMemoryMetrics

CANON_CONNECTOR_OBSERVABILITY = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _metric_status(value: str) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return 'unknown'
    return ''.join(ch if ch.isalnum() else '_' for ch in text).strip('_') or 'unknown'


@dataclass(frozen=True)
class ConnectorExecutionEvent:
    tenant_id: str
    connector_id: str
    provider: str = ''
    version: str = ''
    operation: str = ''
    status: str = ''
    trace_id: str | None = None
    duration_ms: float | None = None
    fallback_depth: int = 0
    route_index: int = 0
    attempt: int = 0
    breaker_state: str | None = None
    recorded_at: datetime = field(default_factory=utc_now)
    payload: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')
        if not str(self.version or '').strip():
            raise ValueError('version is required')
        if not str(self.operation or '').strip():
            raise ValueError('operation is required')
        if not str(self.status or '').strip():
            raise ValueError('status is required')
        if self.recorded_at.tzinfo is None:
            raise ValueError('recorded_at must be timezone-aware')
        if self.duration_ms is not None and float(self.duration_ms) < 0:
            raise ValueError('duration_ms must be >= 0')
        if int(self.fallback_depth) < 0:
            raise ValueError('fallback_depth must be >= 0')
        if int(self.route_index) < 0:
            raise ValueError('route_index must be >= 0')
        if int(self.attempt) < 0:
            raise ValueError('attempt must be >= 0')


class ConnectorObservability:
    def __init__(
        self,
        *,
        metrics: InMemoryMetrics | None = None,
        audit_log: ActionAuditLog | None = None,
    ) -> None:
        self._metrics = metrics or InMemoryMetrics()
        self._audit_log = audit_log or build_default_action_audit_log()

    @property
    def metrics(self) -> InMemoryMetrics:
        return self._metrics

    @property
    def audit_log(self) -> ActionAuditLog:
        return self._audit_log

    def record(self, event: ConnectorExecutionEvent) -> None:
        event.validate()
        status_slug = _metric_status(event.status)
        labels = {
            'route_index': str(int(event.route_index)),
            'attempt': str(int(event.attempt)),
            'connector_id': str(event.connector_id),
            'provider': str(event.provider or 'unknown'),
            'version': str(event.version),
            'operation': str(event.operation),
            'status': str(event.status),
        }
        self._metrics.inc('connector.calls.total', tenant_id=event.tenant_id, labels=labels)
        self._metrics.inc(f'connector.calls.status.{status_slug}', tenant_id=event.tenant_id, labels=labels)
        if event.fallback_depth > 0:
            self._metrics.inc('connector.failover.total', tenant_id=event.tenant_id, labels=labels)
        if status_slug == 'blocked':
            self._metrics.inc('connector.blocked.total', tenant_id=event.tenant_id, labels=labels)
        if 'timeout' in status_slug:
            self._metrics.inc('connector.timeout.total', tenant_id=event.tenant_id, labels=labels)
        if 'retry' in status_slug:
            self._metrics.inc('connector.retry.total', tenant_id=event.tenant_id, labels=labels)
        if 'circuit' in status_slug or 'half_open' in status_slug:
            self._metrics.inc('connector.breaker.total', tenant_id=event.tenant_id, labels=labels)
        if event.duration_ms is not None:
            self._metrics.observe('connector.duration_ms', float(event.duration_ms), tenant_id=event.tenant_id, labels=labels)
        self._metrics.set_gauge('connector.fallback_depth', float(event.fallback_depth), tenant_id=event.tenant_id, labels=labels)
        self._metrics.set_gauge('connector.route_index', float(event.route_index), tenant_id=event.tenant_id, labels=labels)
        self._metrics.set_gauge('connector.attempt', float(event.attempt), tenant_id=event.tenant_id, labels=labels)
        self._audit_log.record(
            {
                'kind': 'connector_execution',
                'tenant_id': str(event.tenant_id),
                'connector_id': str(event.connector_id),
                'provider': str(event.provider or 'unknown'),
                'version': str(event.version),
                'operation': str(event.operation),
                'status': str(event.status),
                'status_slug': status_slug,
                'trace_id': None if event.trace_id is None else str(event.trace_id),
                'duration_ms': None if event.duration_ms is None else float(event.duration_ms),
                'fallback_depth': int(event.fallback_depth),
                'route_index': int(event.route_index),
                'attempt': int(event.attempt),
                'breaker_state': None if event.breaker_state is None else str(event.breaker_state),
                'recorded_at': event.recorded_at.isoformat(),
                'payload': dict(event.payload or {}),
            }
        )


__all__ = [
    'CANON_CONNECTOR_OBSERVABILITY',
    'ConnectorExecutionEvent',
    'ConnectorObservability',
]
