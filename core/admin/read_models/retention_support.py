from __future__ import annotations

from typing import Any
from collections.abc import Iterable

from core.admin.read_models.common_support import iter_events_bounded, resolve_now_ms, supports_kwarg


def iter_events_window(event_store: Any, *, tenant_id: str, start_ms: int, end_ms: int) -> Iterable[dict[str, Any]]:
    return iter_events_bounded(event_store, tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms))


__all__ = ["iter_events_window", "resolve_now_ms", "supports_kwarg"]
