from __future__ import annotations

from typing import Any


def resolve_tenant(event_log: Any) -> str:
    tenant = getattr(event_log, "_tenant", None)
    tenant_id = getattr(tenant, "tenant_id", None)
    if tenant_id:
        return str(tenant_id).strip()
    return str(getattr(event_log, "tenant_id", None) or "").strip()
