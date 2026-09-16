from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any, Protocol

from core.events.event_types import (
    PAYMENT_CAPTURED,
    PAYMENT_CHECKED,
    PAYMENT_CREATED,
    PAYMENT_FAILED,
    PAYMENT_SUCCEEDED,
)
from core.events.read_model_support import best_effort_latest_event
from core.payments.contracts import PAYMENT_SCHEMA_VERSION, Payment, PaymentIdentity, PaymentLifecycleStatus
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


CANON_PAYMENT_PROJECTOR = True
_CANONICAL_PAYMENT_EVENTS = frozenset({
    PAYMENT_CREATED, PAYMENT_CHECKED, PAYMENT_SUCCEEDED, PAYMENT_CAPTURED, PAYMENT_FAILED
})


class PaymentNotFound(LookupError):
    pass


class PaymentHistoryInvariantViolation(RuntimeError):
    pass


def _canonical_payment_metadata(payload: dict[str, Any]) -> dict[str, str]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise PaymentHistoryInvariantViolation("canonical payment metadata is missing")
    result = {
        key: str(metadata.get(key) or "").strip()
        for key in ("tenant_id", "business_id", "product_id", "order_id")
    }
    if any(not value for value in result.values()):
        raise PaymentHistoryInvariantViolation("canonical payment scope is incomplete")
    return result


class PaymentProjector:
    """Read-only projector for schema-v2 business-scoped payment chronology."""

    def __init__(self, event_store: EventStoreLike) -> None:
        self._events = event_store

    def _events_for_business(
        self, *, tenant_id: str, business_id: str, external_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for append_order, event in enumerate(
            self._events.iter_events(
                tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=None
            )
        ):
            event_type = str(event.get("event_type") or event.get("type") or "")
            if event_type not in _CANONICAL_PAYMENT_EVENTS:
                continue
            payload = event.get("payload")
            payload = dict(payload) if isinstance(payload, dict) else {}
            ext = str(payload.get("external_id") or "").strip()
            if external_id is not None and ext and ext != str(external_id):
                continue
            raw_metadata = payload.get("metadata")
            raw_business = (
                str(raw_metadata.get("business_id") or "").strip()
                if isinstance(raw_metadata, dict)
                else ""
            )
            if raw_business and raw_business != str(business_id):
                continue
            schema = payload.get("schema_version")
            if schema is None:
                continue  # Explicitly legacy/non-authoritative chronology.
            if int(schema) != PAYMENT_SCHEMA_VERSION:
                raise PaymentHistoryInvariantViolation("unsupported canonical payment schema")
            if str(event.get("source") or "") != "payments":
                raise PaymentHistoryInvariantViolation("canonical payment event has a non-canonical source")
            metadata = _canonical_payment_metadata(payload)
            if metadata["tenant_id"] != str(tenant_id):
                raise PaymentHistoryInvariantViolation("canonical payment tenant scope conflicts")
            if metadata["business_id"] != str(business_id):
                continue
            if not ext:
                raise PaymentHistoryInvariantViolation("canonical payment external_id is missing")
            rows.append({
                "append_order": append_order,
                "timestamp_ms": int(event.get("timestamp_ms") or 0),
                "event_type": event_type,
                "payload": payload,
                "metadata": metadata,
                "external_id": ext,
            })
        rows.sort(key=lambda row: (row["timestamp_ms"], row["append_order"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, external_id: str) -> Payment:
        rows = self._events_for_business(
            tenant_id=tenant_id, business_id=business_id, external_id=external_id
        )
        if not rows:
            raise PaymentNotFound(f"canonical payment not found: {external_id}")
        created = [row for row in rows if row["event_type"] == PAYMENT_CREATED]
        if len(created) != 1 or rows[0] is not created[0]:
            raise PaymentHistoryInvariantViolation(
                "canonical payment history must begin with exactly one created event"
            )
        first = created[0]
        payload = first["payload"]
        metadata = first["metadata"]
        try:
            identity = PaymentIdentity(
                tenant_id=metadata["tenant_id"],
                business_id=metadata["business_id"],
                product_id=metadata["product_id"],
                order_id=metadata["order_id"],
                provider=str(payload.get("provider") or ""),
                external_id=first["external_id"],
                schema_version=int(payload["schema_version"]),
            )
            amount = int(payload.get("amount") or 0)
            currency = str(payload.get("currency") or "")
            created_at = int(first["timestamp_ms"])
            payment = Payment(
                identity=identity,
                amount_minor=amount,
                currency=currency,
                created_at_ms=created_at,
                updated_at_ms=created_at,
            )
        except (TypeError, ValueError) as exc:
            raise PaymentHistoryInvariantViolation("canonical payment created payload is invalid") from exc

        for row in rows[1:]:
            metadata = row["metadata"]
            if (
                metadata["tenant_id"] != payment.identity.tenant_id
                or metadata["business_id"] != payment.identity.business_id
                or metadata["product_id"] != payment.identity.product_id
                or metadata["order_id"] != payment.identity.order_id
            ):
                raise PaymentHistoryInvariantViolation("canonical payment immutable scope changed")
            when = int(row["timestamp_ms"])
            event_type = row["event_type"]
            if payment.terminal_at_ms is not None:
                raise PaymentHistoryInvariantViolation("canonical payment history continues after terminal proof")
            if event_type == PAYMENT_CREATED:
                raise PaymentHistoryInvariantViolation("canonical payment has duplicate create event")
            if event_type == PAYMENT_CHECKED:
                next_status = (
                    payment.lifecycle_status
                    if payment.lifecycle_status is PaymentLifecycleStatus.SUCCEEDED
                    else PaymentLifecycleStatus.CHECKED
                )
                payment = replace(
                    payment, lifecycle_status=next_status, updated_at_ms=max(payment.updated_at_ms, when)
                )
                continue
            if event_type == PAYMENT_SUCCEEDED:
                if payment.lifecycle_status is PaymentLifecycleStatus.FAILED:
                    raise PaymentHistoryInvariantViolation("failed payment cannot succeed")
                payment = replace(
                    payment,
                    lifecycle_status=PaymentLifecycleStatus.SUCCEEDED,
                    updated_at_ms=max(payment.updated_at_ms, when),
                )
                continue
            if event_type == PAYMENT_CAPTURED:
                if payment.lifecycle_status is not PaymentLifecycleStatus.SUCCEEDED:
                    raise PaymentHistoryInvariantViolation("payment capture requires succeeded state")
                payment = replace(
                    payment,
                    updated_at_ms=max(payment.updated_at_ms, when),
                    terminal_at_ms=when,
                    captured_at_ms=when,
                )
                continue
            if event_type == PAYMENT_FAILED:
                if payment.lifecycle_status is PaymentLifecycleStatus.SUCCEEDED:
                    raise PaymentHistoryInvariantViolation("succeeded payment cannot fail")
                payment = replace(
                    payment,
                    lifecycle_status=PaymentLifecycleStatus.FAILED,
                    updated_at_ms=max(payment.updated_at_ms, when),
                    terminal_at_ms=when,
                )
                continue
            raise PaymentHistoryInvariantViolation("canonical payment history contains unknown transition")
        return payment

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Payment, ...]:
        ids = sorted({
            str(row["external_id"])
            for row in self._events_for_business(tenant_id=tenant_id, business_id=business_id)
            if row["event_type"] == PAYMENT_CREATED
        })
        return tuple(
            self.get(tenant_id=tenant_id, business_id=business_id, external_id=external_id)
            for external_id in ids
        )
