from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

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
    ) -> Iterable[dict[str, Any]]: ...


def compute_entitlements(
    *,
    event_store: EventStoreLike,
    tenant_id: str = "default",
    user_id: str,
) -> dict[str, Any]:
    """Compute entitlements inside one tenant/user isolation boundary.

    New writes use ``entitlement_granted``. ``access_granted`` stays readable
    only for historical compatibility.
    """

    tenant = str(tenant_id)
    uid = str(user_id)
    event_types = ("entitlement_granted", "access_granted")
    wm = watermark_for(
        event_store,
        tenant_id=tenant,
        user_id=uid,
        event_types=event_types,
    )

    def _compute() -> dict[str, Any]:
        event = best_effort_latest_event(
            event_store=event_store,
            where="core/entitlements/read_model.compute_entitlements",
            tenant_id=tenant,
            user_id=uid,
            event_types=event_types,
            legacy_event_type="access_granted",
        )
        if event:
            payload = event.get("payload") or {}
            if bool(payload.get("full_access", True)):
                return {"full_access": True}

        full_access = False
        for event_type in event_types:
            for event in event_store.iter_events(
                tenant_id=tenant,
                start_ms=0,
                end_ms=None,
                event_type=event_type,
                user_id=uid,
            ):
                payload = event.get("payload") or {}
                if bool(payload.get("full_access", True)):
                    full_access = True
        return {"full_access": bool(full_access)}

    return global_cache().get(
        key=("entitlements", tenant, uid),
        compute=_compute,
        watermark_ms=wm,
    )
