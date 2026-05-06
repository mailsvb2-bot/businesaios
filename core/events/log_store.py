from __future__ import annotations

from core.events.store_call import call_append_event


def append_event_dict(*, store, batch_depth: int, metrics, tenant_id: str, event_dict: dict) -> None:
    if not isinstance(event_dict, dict):
        raise ValueError("event_dict must be dict")
    if event_dict.get("tenant_id") is None:
        event_dict["tenant_id"] = str(tenant_id)
    tid = str(event_dict.get("tenant_id") or "").strip()
    if not tid:
        raise ValueError("tenant_id is required for events (strict)")
    if tid != str(tenant_id):
        raise ValueError("cross-tenant event write blocked")

    if hasattr(store, "append_event"):
        try:
            call_append_event(
                append_fn=store.append_event,
                event_dict=event_dict,
                commit=(batch_depth == 0),
            )
        except Exception:
            metrics.on_append_failure()
            raise
        return

    try:
        store.append(event_dict)
    except Exception:
        metrics.on_append_failure()
        raise
