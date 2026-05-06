from __future__ import annotations

"""Canonical security audit facade over immutable storage."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from observability.audit_event_schema import AuditCategory, AuditSeverity
from observability.immutable_event_store import ImmutableEventStore


CANON_SECURITY_AUDIT_LOG = True
_ALLOWED_SEVERITY = {item.value for item in AuditSeverity}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SecurityAuditLog:
    store: ImmutableEventStore
    allowed_category: AuditCategory = AuditCategory.SECURITY

    def append(
        self,
        *,
        tenant_id: str,
        event_type: str,
        severity: str = AuditSeverity.WARNING.value,
        actor_id: str | None = None,
        subject_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        emitted_at: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        event_type_text = str(event_type or '').strip()
        if '.' not in event_type_text:
            raise ValueError('event_type must be namespaced')
        severity_text = str(severity or '').strip().lower()
        if severity_text not in _ALLOWED_SEVERITY:
            raise ValueError('severity is not allowed')
        normalized_payload = dict(payload or {})
        normalized_payload['category'] = self.allowed_category.value
        if actor_id is not None:
            normalized_payload['actor_id'] = str(actor_id)
        if subject_id is not None:
            normalized_payload['subject_id'] = str(subject_id)
        normalized_payload['severity'] = severity_text
        record = self.store.append(
            event_id=str(event_id or uuid4()),
            tenant_id=tenant_id,
            event_type=event_type_text,
            emitted_at=str(emitted_at or utc_now_iso()),
            payload=normalized_payload,
        )
        return dict(record.__dict__)

    def integrity_summary(self) -> dict[str, Any]:
        try:
            self.store.validate_chain()
            events = self.store.read_events()
            return {
                'checked': True,
                'valid': True,
                'event_count': len(events),
                'chain_head': events[-1].record_hash if events else 'GENESIS',
                'error': None,
            }
        except Exception as exc:
            events = self.store.read_events()
            return {
                'checked': True,
                'valid': False,
                'event_count': len(events),
                'chain_head': events[-1].record_hash if events else 'GENESIS',
                'error': str(exc),
            }


__all__ = [
    'CANON_SECURITY_AUDIT_LOG',
    'SecurityAuditLog',
    'utc_now_iso',
]
