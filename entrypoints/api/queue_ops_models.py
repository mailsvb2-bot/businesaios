from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CANON_API_QUEUE_OPS_MODELS = True


def _clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_clone(item) for item in value)
    if isinstance(value, list):
        return tuple(_clone(item) for item in value)
    return value


@dataclass(frozen=True)
class QueueOpsAuditQuery:
    tenant_id: str
    queue_name: str
    limit: int = 50
    action: str | None = None
    status: str | None = None
    source: str | None = None
    timeline_limit: int = 25


@dataclass(frozen=True)
class QueueRemediationExecuteCommand:
    tenant_id: str
    queue_name: str
    hook_code: str
    actor_id: str | None = None
    request_id: str | None = None
    source: str = 'control_plane'


@dataclass(frozen=True)
class QueueOpsViewResponse:
    tenant_id: str
    queue_name: str
    health: dict[str, Any]
    alerts: tuple[dict[str, Any], ...]
    rollup_summary: dict[str, Any] | None
    remediation_plan: dict[str, Any]
    analytics_preview: dict[str, Any] | None = None
    audit_preview: dict[str, Any] | None = None
    operator_summary: dict[str, Any] | None = None
    timeline_preview: tuple[dict[str, Any], ...] | None = None
    approval_preview: dict[str, Any] | None = None
    trend_preview: dict[str, Any] | None = None
    data_freshness: dict[str, Any] | None = None
    evidence_timeline: tuple[dict[str, Any], ...] | None = None
    consistency: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'queue_name': self.queue_name,
            'health': _clone(self.health),
            'alerts': _clone(self.alerts),
            'rollup_summary': None if self.rollup_summary is None else _clone(self.rollup_summary),
            'remediation_plan': _clone(self.remediation_plan),
            'analytics_preview': None if self.analytics_preview is None else _clone(self.analytics_preview),
            'audit_preview': None if self.audit_preview is None else _clone(self.audit_preview),
            'operator_summary': None if self.operator_summary is None else _clone(self.operator_summary),
            'timeline_preview': None if self.timeline_preview is None else _clone(self.timeline_preview),
            'approval_preview': None if self.approval_preview is None else _clone(self.approval_preview),
            'trend_preview': None if self.trend_preview is None else _clone(self.trend_preview),
            'data_freshness': None if self.data_freshness is None else _clone(self.data_freshness),
            'evidence_timeline': None if self.evidence_timeline is None else _clone(self.evidence_timeline),
            'consistency': None if self.consistency is None else _clone(self.consistency),
        }


@dataclass(frozen=True)
class QueueRemediationAuditResponse:
    tenant_id: str
    queue_name: str
    plans: tuple[dict[str, Any], ...]
    executions: tuple[dict[str, Any], ...]
    route_history: tuple[dict[str, Any], ...]
    timeline: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'queue_name': self.queue_name,
            'plans': _clone(self.plans),
            'executions': _clone(self.executions),
            'route_history': _clone(self.route_history),
            'timeline': _clone(self.timeline),
        }


@dataclass(frozen=True)
class QueueRemediationExecutionResponse:
    tenant_id: str
    queue_name: str
    hook_code: str
    executed: bool
    reason: str
    executed_at: str
    route_recorded: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'queue_name': self.queue_name,
            'hook_code': self.hook_code,
            'executed': self.executed,
            'reason': self.reason,
            'executed_at': self.executed_at,
            'route_recorded': self.route_recorded,
        }


@dataclass(frozen=True)
class QueueRemediationAnalyticsResponse:
    tenant_id: str
    queue_name: str
    analytics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'queue_name': self.queue_name,
            'analytics': _clone(self.analytics),
        }


__all__ = [
    'CANON_API_QUEUE_OPS_MODELS',
    'QueueOpsAuditQuery',
    'QueueOpsViewResponse',
    'QueueRemediationAuditResponse',
    'QueueRemediationExecuteCommand',
    'QueueRemediationExecutionResponse',
    'QueueRemediationAnalyticsResponse',
]
