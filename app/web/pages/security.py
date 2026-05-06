from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import AuditLogTable
from app.web.components import SecurityEventsCard
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_SECURITY_PAGE = True


@dataclass(frozen=True, slots=True)
class SecurityPage:
    security_events_card: SecurityEventsCard = field(default_factory=SecurityEventsCard)
    audit_log_table: AuditLogTable = field(default_factory=AuditLogTable)
    kind: str = 'security_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Security',
                'security_events': normalized.get('security_events'),
                'audit_table': normalized.get('audit_table'),
                'tenant_bound': True,
            },
        )

    def build_from_events(self, *, tenant_id: str, events: Iterable[Any], limit: int = 100) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        security_events = self.security_events_card.build_from_events(tenant_id=required_tenant_id, events=events, limit=min(50, max(1, int(limit))))
        audit_table = self.audit_log_table.build_from_events(tenant_id=required_tenant_id, events=events, category='security', limit=limit)
        return self.build({'tenant_id': required_tenant_id, 'security_events': security_events, 'audit_table': audit_table})


__all__ = ['SecurityPage', 'CANON_WEB_SECURITY_PAGE']
