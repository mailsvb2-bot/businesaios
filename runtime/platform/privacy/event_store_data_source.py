from __future__ import annotations

"""Platform-layer adapter: event store as a user-data source.

IMPORTANT:
- platform_layer must NOT import core.* (layering lock).
- Therefore we accept a duck-typed event store with minimal required methods.

Required event_store methods:
- iter_events(tenant_id=..., start_ms=..., end_ms=..., user_id=..., event_type=...)
- delete_user_events(tenant_id=..., user_id=...)

This adapter is used by core/privacy services via dependency injection.
"""

from dataclasses import dataclass
from typing import Any, Dict
from collections.abc import Iterable

_PLACEHOLDER_TENANTS = {"", "default", "legacy", "none", "null"}


def _require_tenant_id(value: Any) -> str:
    tenant_id = str(value or "").strip()
    if tenant_id.lower() in _PLACEHOLDER_TENANTS:
        raise ValueError("tenant_id is required (strict)")
    return tenant_id


@dataclass(frozen=True)
class EventStoreUserDataSource:
    event_store: Any

    def export(self, req) -> Iterable[dict[str, Any]]:  # req is core.privacy.data_rights.DataExportRequest
        tenant_id = _require_tenant_id(getattr(req, 'tenant_id', ''))
        user_id = str(getattr(req, 'user_id', '') or '')
        start_ms = int(getattr(req, 'start_ms', 0) or 0)
        end_ms = getattr(req, 'end_ms', None)
        if end_ms is not None:
            end_ms = int(end_ms)
        yield from self.event_store.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id)

    def delete(self, req) -> int:  # req is core.privacy.data_rights.DataDeleteRequest
        tenant_id = _require_tenant_id(getattr(req, 'tenant_id', ''))
        user_id = str(getattr(req, 'user_id', '') or '')
        return int(self.event_store.delete_user_events(tenant_id=tenant_id, user_id=user_id))
