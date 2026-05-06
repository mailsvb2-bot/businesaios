from __future__ import annotations

from typing import Any

from .tenant import resolve_tenant


def emit(event_log: Any, event_name: str, **kwargs):
    emit_fn = getattr(event_log, "emit", None)
    if emit_fn is None:
        return None

    tenant_id = resolve_tenant(event_log)
    try:
        if tenant_id and not getattr(event_log, "_tenant", None):
            try:
                return emit_fn(event_type=event_name, tenant_id=tenant_id, **kwargs)
            except TypeError:
                pass
        return emit_fn(event_type=event_name, **kwargs)
    except Exception:
        return None
