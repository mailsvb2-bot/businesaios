from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Mapping

from advisory.revenue_os.contracts import _required_text, _utc_datetime

CANON_ADVISORY_REVENUE_OS_AUDIT_EVENTS = True


@dataclass(frozen=True, slots=True)
class RevenueAuditEvent:
    event_type: str
    observed_at: datetime
    tenant_id: str
    product_id: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def normalized_copy(self) -> 'RevenueAuditEvent':
        return replace(
            self,
            event_type=_required_text(self.event_type, field_name='event_type'),
            observed_at=_utc_datetime(self.observed_at, field_name='observed_at'),
            tenant_id=_required_text(self.tenant_id, field_name='tenant_id'),
            product_id=_required_text(self.product_id, field_name='product_id'),
            payload=dict(self.payload),
        )

    def to_record(self) -> dict[str, object]:
        normalized = self.normalized_copy()
        return {
            'event_type': normalized.event_type,
            'observed_at': normalized.observed_at.isoformat(),
            'tenant_id': normalized.tenant_id,
            'product_id': normalized.product_id,
            'payload': dict(normalized.payload),
        }


__all__ = ['CANON_ADVISORY_REVENUE_OS_AUDIT_EVENTS', 'RevenueAuditEvent']
