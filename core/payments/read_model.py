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


def _payment_product_id(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        product_id = str(metadata.get("product_id") or "").strip()
        if product_id:
            return product_id
    return str(payload.get("product_id") or "").strip()


def latest_payment_status(
    *,
    event_store: EventStoreLike,
    tenant_id: str = "default",
    user_id: str,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Return latest payment status inside one tenant/product/user boundary.

    Omitting ``product_id`` produces an explicit administrative aggregate view.
    Authorization or product-specific UI must always provide the product scope.
    """

    tenant = str(tenant_id).strip()
    uid = str(user_id).strip()
    product = str(product_id or "").strip() or None
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

    def _result_from_event(event: dict[str, Any]) -> dict[str, Any]:
        event_type = str(event.get("event_type") or event.get("type") or "")
        payload = event.get("payload")
        payload = dict(payload) if isinstance(payload, dict) else {}
        if event_type == "payment_succeeded":
            status = "succeeded"
        elif event_type == "payment_failed":
            status = "failed"
        elif event_type in {"payment_created", "payment_captured"}:
            status = str(payload.get("status") or "pending").lower()
        else:
            status = "unknown"

        result = {"status": status, **payload}
        if product is not None:
            result["product_id"] = product
        else:
            result["scope"] = "aggregate_admin_view"
        return result

    def _compute() -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []

        # Administrative aggregate reads retain compatibility with stores that
        # expose only the canonical latest-event API. Product-scoped reads do
        # not use this fallback because one unscoped latest event cannot prove
        # ownership by the requested product.
        if product is None:
            for event_type in event_types:
                latest = best_effort_latest_event(
                    event_store=event_store,
                    where="core/payments/read_model.latest_payment_status",
                    tenant_id=tenant,
                    user_id=uid,
                    event_types=(event_type,),
                    legacy_event_type=event_type,
                )
                if latest is not None:
                    candidates.append(latest)

        for event in event_store.iter_events(
            tenant_id=tenant,
            start_ms=0,
            end_ms=None,
            event_type=None,
            user_id=uid,
        ):
            event_type = str(event.get("event_type") or event.get("type") or "")
            if event_type not in event_types:
                continue
            payload = event.get("payload")
            payload = dict(payload) if isinstance(payload, dict) else {}
            event_product = _payment_product_id(payload)
            if product is not None and event_product != product:
                continue
            candidates.append(dict(event))

        if not candidates:
            result = {"status": "none"}
            if product is not None:
                result["product_id"] = product
            else:
                result["scope"] = "aggregate_admin_view"
            return result

        latest = max(
            candidates,
            key=lambda event: int(event.get("timestamp_ms") or 0),
        )
        return _result_from_event(latest)

    return global_cache().get(
        key=("payment_status", tenant, product or "*", uid),
        compute=_compute,
        watermark_ms=wm,
    )
