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
    product_id: str | None = None,
) -> dict[str, Any]:
    """Compute entitlements inside one tenant/product/user boundary.

    ``product_id`` must be supplied for an authorization decision. Omitting it
    returns an explicit administrative aggregate only; it must not be used to
    authorize access to a particular product.

    New writes use ``entitlement_granted``. Historical ``access_granted`` events
    remain readable, but an unscoped legacy event is never promoted into a
    product-specific entitlement.
    """

    tenant = str(tenant_id).strip()
    uid = str(user_id).strip()
    product = str(product_id or "").strip() or None
    event_types = ("entitlement_granted", "access_granted")
    wm = watermark_for(
        event_store,
        tenant_id=tenant,
        user_id=uid,
        event_types=event_types,
    )

    def _compute() -> dict[str, Any]:
        full_access = False
        granted_products: set[str] = set()
        events: list[dict[str, Any]] = []

        # Administrative aggregate reads retain compatibility with stores that
        # expose only the canonical latest-event API. Product authorization does
        # not use this fallback because a single latest event cannot prove that
        # an earlier grant belongs to the requested product.
        if product is None:
            for event_type in event_types:
                latest = best_effort_latest_event(
                    event_store=event_store,
                    where="core/entitlements/read_model.compute_entitlements",
                    tenant_id=tenant,
                    user_id=uid,
                    event_types=(event_type,),
                    legacy_event_type=event_type,
                )
                if latest is not None:
                    events.append(latest)

        for event_type in event_types:
            events.extend(
                event_store.iter_events(
                    tenant_id=tenant,
                    start_ms=0,
                    end_ms=None,
                    event_type=event_type,
                    user_id=uid,
                )
            )

        for event in events:
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            event_product = str(payload.get("product_id") or "").strip()
            if product is not None and event_product != product:
                continue
            if not bool(payload.get("full_access", True)):
                continue
            full_access = True
            if event_product:
                granted_products.add(event_product)

        if product is not None:
            return {
                "full_access": bool(full_access),
                "product_id": product,
            }
        return {
            "full_access": bool(full_access),
            "product_ids": sorted(granted_products),
            "scope": "aggregate_admin_view",
        }

    return global_cache().get(
        key=("entitlements", tenant, product or "*", uid),
        compute=_compute,
        watermark_ms=wm,
    )
