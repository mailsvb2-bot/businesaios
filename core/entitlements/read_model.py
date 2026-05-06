from __future__ import annotations

from typing import Any, Dict, Iterable, Protocol

from core.events.read_model_support import best_effort_latest_event
from core.read_model.cache import global_cache, watermark_for


class EventStoreLike(Protocol):
    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
    ) -> Iterable[Dict[str, Any]]: ...


def compute_entitlements(*, event_store: EventStoreLike, tenant_id: str = "default", user_id: str) -> Dict[str, Any]:
    """Compute entitlements for a user from events.

    MVP rules:
    - access_granted(full_access=True) => full_access=True
    """
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=str(tenant_id), user_id=uid, event_types=("access_granted",))

    def _compute() -> Dict[str, Any]:
        # Fast-path: if there is any access_granted with full_access=True.
        ev = best_effort_latest_event(
            event_store=event_store,
            where='core/entitlements/read_model.compute_entitlements',
            tenant_id=str(tenant_id),
            user_id=uid,
            event_types=("access_granted",),
            legacy_event_type="access_granted",
        )
        if ev:
            payload = ev.get("payload") or {}
            if bool(payload.get("full_access", True)):
                return {"full_access": True}

        full_access = False
        for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type="access_granted", user_id=uid):
            payload = ev.get("payload") or {}
            if bool(payload.get("full_access", True)):
                full_access = True
        return {"full_access": bool(full_access)}

    return global_cache().get(key=("entitlements", uid), compute=_compute, watermark_ms=wm)