from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Protocol

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


def latest_payment_status(*, event_store: EventStoreLike, tenant_id: str = "default", user_id: str) -> dict[str, Any]:
    """Return latest known payment status for user.

    This is a best-effort event-sourced read model.
    """
    uid = str(user_id)
    wm = watermark_for(
        event_store,
        tenant_id=str(tenant_id),
        user_id=uid,
        event_types=("payment_created", "payment_succeeded", "payment_failed", "payment_captured"),
    )

    def _compute() -> dict[str, Any]:
        # Fast-path: prefer DB-side latest-event lookup if available.
        latest: dict[str, Any] | None = best_effort_latest_event(
            event_store=event_store,
            where='core/payments/read_model.latest_payment_status',
            tenant_id=str(tenant_id),
            user_id=uid,
            event_types=("payment_created", "payment_succeeded", "payment_failed", "payment_captured"),
            legacy_event_type="payment_created",
        )

        if latest is None:
            for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=None, user_id=uid):
                if ev.get("event_type") in {"payment_created", "payment_succeeded", "payment_failed", "payment_captured"}:
                    latest = ev
        if not latest:
            return {"status": "none"}
        et = str(latest.get("event_type"))
        payload = latest.get("payload") or {}
        if et == "payment_succeeded":
            return {"status": "succeeded", **(payload if isinstance(payload, dict) else {})}
        if et in {"payment_failed"}:
            return {"status": "failed", **(payload if isinstance(payload, dict) else {})}
        if et in {"payment_created", "payment_captured"}:
            st = str(payload.get("status") or "pending")
            return {"status": st.lower(), **(payload if isinstance(payload, dict) else {})}
        return {"status": "unknown"}

    return global_cache().get(key=("payment_status", uid), compute=_compute, watermark_ms=wm)
