from __future__ import annotations

from typing import Any, Iterable

from core.admin.read_models.common_support import iter_events_bounded, resolve_now_ms


def iter_pricing_events(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    end_ms: int,
) -> Iterable[dict[str, Any]]:
    return iter_events_bounded(event_store, tenant_id=str(tenant_id), end_ms=int(end_ms), event_type=str(event_type))


__all__ = ["iter_pricing_events", "resolve_now_ms"]
