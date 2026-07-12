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


def latest_payment_status(
    *,
    event_store: EventStoreLike,
    tenant_id: str = "default",
    user_id: str,
) -> dict[str, Any]:
    """Return latest payment status inside one tenant/user boundary."""

    tenant = str(tenant_id)
    uid = str(user_id)
    event_types = (
        "payment_created",
        "payment_succeeded",
        "payment_failed",
        "payment_captured",
    )
    wm = watermark_for(
        event_store,
        tenant_id=tenant,
        user_id=uid,
        event_types=event_types,
    )

    def _compute() -> dict[str, Any]:
        latest: dict[str, Any] | None = best_effort_latest_event(
            event_store=event_store,
            where="core/payments/read_model.latest_payment_status",
            tenant_id=tenant,
            user_id=uid,
            event_types=event_types,
            legacy_event_type="payment_created",
        )

        if latest is None:
            for event in event_store.iter_events(
                tenant_id=tenant,
                start_ms=0,
                end_ms=None,
                event_type=None,
                user_id=uid,
            ):
                if event.get("event_type") in set(event_types):
                    latest = event
        if not latest:
            return {"status": "none"}

        event_type = str(latest.get("event_type"))
        payload = latest.get("payload") or {}
        if event_type == "payment_succeeded":
            return {"status": "succeeded", **(payload if isinstance(payload, dict) else {})}
        if event_type == "payment_failed":
            return {"status": "failed", **(payload if isinstance(payload, dict) else {})}
        if event_type in {"payment_created", "payment_captured"}:
            status = str(payload.get("status") or "pending")
            return {"status": status.lower(), **(payload if isinstance(payload, dict) else {})}
        return {"status": "unknown"}

    return global_cache().get(
        key=("payment_status", tenant, uid),
        compute=_compute,
        watermark_ms=wm,
    )
