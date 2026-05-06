from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmAuditEvent:
    event_type: str
    provider_key: str
    tenant_id: str
    business_id: str
    record_id: str | None = None
