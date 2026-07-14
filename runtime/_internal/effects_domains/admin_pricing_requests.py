from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUEST_EVENT = "admin_pricing_change_requested"
TERMINAL_EVENTS = {
    "admin_pricing_change_applied",
    "admin_pricing_change_rejected",
}


@dataclass(frozen=True)
class PricingChangeRequest:
    request_id: str
    tenant_id: str
    product_id: str
    environment: str
    offer_id: str
    plan_id: int | None
    new_price: int
    suggested_pricing_version: str
    requested_by: str


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "")


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _events(event_log: Any) -> list[dict[str, Any]]:
    iterator = getattr(event_log, "iter_events", None)
    if not callable(iterator):
        raise RuntimeError("PRICING_EVENT_LOG_READ_REQUIRED")
    return [dict(event) for event in iterator() if isinstance(event, dict)]


def resolve_pricing_change_request(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> PricingChangeRequest:
    tenant = str(tenant_id or "").strip()
    request = str(request_id or "").strip()
    if not tenant:
        raise RuntimeError("TENANT_ID_REQUIRED")
    if not request:
        raise RuntimeError("REQUEST_ID_REQUIRED")

    matched: dict[str, Any] | None = None
    for event in _events(event_log):
        if _event_type(event) != REQUEST_EVENT:
            continue
        payload = _payload(event)
        if str(payload.get("request_id") or "").strip() != request:
            continue
        if str(payload.get("tenant_id") or "").strip() != tenant:
            continue
        matched = event

    if matched is None:
        raise RuntimeError(f"PRICING_CHANGE_REQUEST_NOT_FOUND:{tenant}:{request}")

    payload = _payload(matched)
    raw_plan_id = payload.get("plan_id")
    plan_id = int(raw_plan_id) if raw_plan_id is not None else None
    return PricingChangeRequest(
        request_id=request,
        tenant_id=tenant,
        product_id=str(payload.get("product_id") or "").strip(),
        environment=str(payload.get("environment") or "").strip(),
        offer_id=str(payload.get("offer_id") or "").strip(),
        plan_id=plan_id,
        new_price=int(payload.get("new_price")),
        suggested_pricing_version=str(payload.get("suggested_pricing_version") or "").strip(),
        requested_by=str(matched.get("user_id") or "").strip(),
    )


def assert_pricing_request_open(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> None:
    tenant = str(tenant_id or "").strip()
    request = str(request_id or "").strip()
    for event in _events(event_log):
        if _event_type(event) not in TERMINAL_EVENTS:
            continue
        payload = _payload(event)
        if str(payload.get("tenant_id") or "").strip() != tenant:
            continue
        if str(payload.get("request_id") or "").strip() != request:
            continue
        raise RuntimeError(f"PRICING_CHANGE_REQUEST_ALREADY_RESOLVED:{tenant}:{request}")


def validate_pricing_apply_against_request(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
    product_id: str,
    environment: str | None,
    offer_id: str | None,
    plan_id: int | None,
    new_price: int,
    pricing_version: str,
) -> PricingChangeRequest:
    request = resolve_pricing_change_request(
        event_log,
        tenant_id=str(tenant_id),
        request_id=str(request_id),
    )
    assert_pricing_request_open(
        event_log,
        tenant_id=request.tenant_id,
        request_id=request.request_id,
    )

    observed_environment = str(environment or "").strip()
    observed_offer_id = str(offer_id or "").strip()
    mismatches: list[str] = []
    if str(product_id).strip() != request.product_id:
        mismatches.append("product_id")
    if observed_environment != request.environment:
        mismatches.append("environment")
    if observed_offer_id != request.offer_id:
        mismatches.append("offer_id")
    if plan_id != request.plan_id:
        mismatches.append("plan_id")
    if int(new_price) != request.new_price:
        mismatches.append("new_price")
    if request.suggested_pricing_version and str(pricing_version).strip() != request.suggested_pricing_version:
        mismatches.append("pricing_version")
    if mismatches:
        raise RuntimeError(
            "PRICING_CHANGE_REQUEST_MISMATCH:"
            + request.request_id
            + ":"
            + ",".join(sorted(mismatches))
        )
    return request


__all__ = [
    "PricingChangeRequest",
    "assert_pricing_request_open",
    "resolve_pricing_change_request",
    "validate_pricing_apply_against_request",
]
