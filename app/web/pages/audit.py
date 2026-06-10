from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import AuditLogTable
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_AUDIT_PAGE = True


@dataclass(frozen=True, slots=True)
class AuditPage:
    audit_log_table: AuditLogTable = field(default_factory=AuditLogTable)
    kind: str = 'audit_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Audit Log',
                'table': normalized.get('table'),
                'tenant_bound': True,
            },
        )

    def build_from_events(
        self,
        *,
        tenant_id: str,
        events: Iterable[Any],
        category: str | None = None,
        severity: str | None = None,
        event_type_prefix: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        table = self.audit_log_table.build_from_events(
            tenant_id=required_tenant_id,
            events=events,
            category=category,
            severity=severity,
            event_type_prefix=event_type_prefix,
            limit=limit,
        )
        return self.build({'tenant_id': required_tenant_id, 'table': table})


__all__ = ['AuditPage', 'CANON_WEB_AUDIT_PAGE']
