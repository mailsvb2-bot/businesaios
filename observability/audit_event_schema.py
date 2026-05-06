from __future__ import annotations

"""Canonical audit event schema.

CANON_COMPAT_SHIM = True

Audit is immutable evidence.
It must not become business-policy logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id


CANON_AUDIT_EVENT_SCHEMA = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditSeverity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class AuditCategory(str, Enum):
    EXECUTION = 'execution'
    DECISION = 'decision'
    EFFECT = 'effect'
    GOVERNANCE = 'governance'
    SECURITY = 'security'
    OPERATIONS = 'operations'
    INCIDENT = 'incident'
    COMPLIANCE = 'compliance'


@dataclass(frozen=True)
class AuditEventRecord:
    audit_id: str
    tenant_id: str
    event_type: str
    category: AuditCategory
    severity: AuditSeverity
    emitted_at: datetime = field(default_factory=utc_now)
    actor_id: str | None = None
    source_component: str | None = None
    source_namespace: str | None = None
    trace_id: str | None = None
    run_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    correlation_id: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    tags: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.audit_id or '').strip():
            raise ValueError('audit_id is required')
        require_tenant_id(self.tenant_id)
        if not str(self.event_type or '').strip():
            raise ValueError('event_type is required')
        if self.emitted_at.tzinfo is None:
            raise ValueError('emitted_at must be timezone-aware')


def build_execution_audit_event(*, audit_id: str, tenant_id: str, event_type: str, severity: AuditSeverity = AuditSeverity.INFO, trace_id: str | None = None, run_id: str | None = None, decision_id: str | None = None, action_id: str | None = None, correlation_id: str | None = None, source_component: str | None = None, source_namespace: str | None = None, tags: tuple[str, ...] = (), payload: Mapping[str, Any] | None = None) -> AuditEventRecord:
    return AuditEventRecord(
        audit_id=audit_id,
        tenant_id=tenant_id,
        event_type=event_type,
        category=AuditCategory.EXECUTION,
        severity=severity,
        trace_id=trace_id,
        run_id=run_id,
        decision_id=decision_id,
        action_id=action_id,
        correlation_id=correlation_id,
        source_component=source_component,
        source_namespace=source_namespace,
        tags=tags,
        payload=dict(payload or {}),
    )


def build_security_audit_event(*, audit_id: str, tenant_id: str, event_type: str, subject_type: str, subject_id: str, severity: AuditSeverity = AuditSeverity.WARNING, actor_id: str | None = None, source_component: str | None = None, tags: tuple[str, ...] = (), payload: Mapping[str, Any] | None = None) -> AuditEventRecord:
    return AuditEventRecord(
        audit_id=audit_id,
        tenant_id=tenant_id,
        event_type=event_type,
        category=AuditCategory.SECURITY,
        severity=severity,
        actor_id=actor_id,
        source_component=source_component,
        subject_type=subject_type,
        subject_id=subject_id,
        tags=tags,
        payload=dict(payload or {}),
    )


__all__ = [
    'AuditCategory',
    'AuditEventRecord',
    'AuditSeverity',
    'CANON_AUDIT_EVENT_SCHEMA',
    'build_execution_audit_event',
    'build_security_audit_event',
    'utc_now',
]
