from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.platform.config.env_flags import env_bool


@dataclass(frozen=True)
class PricingRequestLifecycle:
    request_event: dict[str, Any]
    request_payload: dict[str, Any]
    rejected_event: dict[str, Any] | None
    applied_event: dict[str, Any] | None

    @property
    def request_id(self) -> str:
        return str(self.request_payload.get("request_id") or "")

    @property
    def requested_by(self) -> str:
        return str(self.request_event.get("user_id") or "")


def _events(event_log: Any) -> tuple[dict[str, Any], ...]:
    try:
        return tuple(dict(event) for event in event_log.iter_events())
    except Exception as exc:
        raise RuntimeError(
            f"PRICING_GOVERNANCE_READ_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc


def _request_id(event: dict[str, Any]) -> str:
    return str((event.get("payload") or {}).get("request_id") or "").strip()


def resolve_pricing_request_lifecycle(
    event_log: Any,
    *,
    request_id: str,
) -> PricingRequestLifecycle:
    rid = str(request_id or "").strip()
    if not rid:
        raise RuntimeError("PRICING_REQUEST_ID_REQUIRED")

    request_event: dict[str, Any] | None = None
    rejected_event: dict[str, Any] | None = None
    applied_event: dict[str, Any] | None = None
    for event in _events(event_log):
        if _request_id(event) != rid:
            continue
        event_type = str(event.get("event_type") or event.get("type") or "")
        if event_type == "admin_pricing_change_requested":
            if request_event is not None:
                current = dict(request_event.get("payload") or {})
                incoming = dict(event.get("payload") or {})
                if current != incoming or str(request_event.get("user_id") or "") != str(event.get("user_id") or ""):
                    raise RuntimeError(f"PRICING_REQUEST_ID_CONFLICT:{rid}")
            request_event = event
        elif event_type == "admin_pricing_change_rejected":
            rejected_event = event
        elif event_type == "admin_pricing_change_applied":
            applied_event = event

    if request_event is None:
        raise RuntimeError(f"PRICING_REQUEST_NOT_FOUND:{rid}")
    return PricingRequestLifecycle(
        request_event=request_event,
        request_payload=dict(request_event.get("payload") or {}),
        rejected_event=rejected_event,
        applied_event=applied_event,
    )


def assert_pricing_request_matches(
    lifecycle: PricingRequestLifecycle,
    *,
    tenant_id: str,
    product_id: str,
    environment: str | None,
    offer_id: str | None,
    plan_id: int | None,
    new_price: int,
) -> None:
    payload = lifecycle.request_payload
    expected = {
        "tenant_id": str(tenant_id),
        "product_id": str(product_id),
        "environment": str(environment or ""),
        "offer_id": str(offer_id or ""),
        "plan_id": int(plan_id) if plan_id is not None else None,
        "new_price": int(new_price),
    }
    actual = {
        "tenant_id": str(payload.get("tenant_id") or ""),
        "product_id": str(payload.get("product_id") or ""),
        "environment": str(payload.get("environment") or ""),
        "offer_id": str(payload.get("offer_id") or ""),
        "plan_id": int(payload["plan_id"]) if payload.get("plan_id") is not None else None,
        "new_price": int(payload.get("new_price") or 0),
    }
    if actual != expected:
        raise RuntimeError(
            f"PRICING_REQUEST_SCOPE_MISMATCH:{lifecycle.request_id}"
        )


def assert_pricing_approval_allowed(
    lifecycle: PricingRequestLifecycle,
    *,
    admin_id: str,
) -> None:
    if lifecycle.rejected_event is not None:
        raise RuntimeError(f"PRICING_REQUEST_REJECTED:{lifecycle.request_id}")
    requested_by = lifecycle.requested_by
    if not requested_by:
        raise RuntimeError(f"PRICING_REQUEST_REQUESTER_MISSING:{lifecycle.request_id}")
    if requested_by == str(admin_id) and not env_bool("ALLOW_SELF_APPROVE", False):
        raise RuntimeError("SELF_APPROVAL_FORBIDDEN")


def assert_pricing_rejection_allowed(
    lifecycle: PricingRequestLifecycle,
) -> None:
    if lifecycle.applied_event is not None:
        raise RuntimeError(f"PRICING_REQUEST_ALREADY_APPLIED:{lifecycle.request_id}")


def pricing_event_evidence(
    *,
    code: str,
    event: dict[str, Any],
    fallback_ref: str,
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "").strip()
    payload = dict(event.get("payload") or {})
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [event_id or str(fallback_ref)],
        "confidence": 1.0,
        "payload": payload,
    }


__all__ = [
    "PricingRequestLifecycle",
    "assert_pricing_approval_allowed",
    "assert_pricing_rejection_allowed",
    "assert_pricing_request_matches",
    "pricing_event_evidence",
    "resolve_pricing_request_lifecycle",
]
