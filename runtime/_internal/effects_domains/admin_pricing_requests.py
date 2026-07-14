from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.platform.config.env_flags import env_bool

REQUEST_EVENT = "admin_pricing_change_requested"
APPLIED_EVENT = "admin_pricing_change_applied"
REJECTED_EVENT = "admin_pricing_change_rejected"
TERMINAL_EVENTS = {APPLIED_EVENT, REJECTED_EVENT}


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
    reason: str


@dataclass(frozen=True)
class PricingRequestLifecycle:
    request_event: dict[str, Any]
    request: PricingChangeRequest
    applied_event: dict[str, Any] | None = None
    rejected_event: dict[str, Any] | None = None

    @property
    def request_id(self) -> str:
        return self.request.request_id

    @property
    def request_payload(self) -> dict[str, Any]:
        return dict(self.request_event.get("payload") or {})

    @property
    def requested_by(self) -> str:
        return self.request.requested_by


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "")


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _events(event_log: Any) -> tuple[dict[str, Any], ...]:
    iterator = getattr(event_log, "iter_events", None)
    if not callable(iterator):
        raise RuntimeError("PRICING_EVENT_LOG_READ_REQUIRED")
    try:
        return tuple(dict(event) for event in iterator() if isinstance(event, dict))
    except Exception as exc:
        raise RuntimeError(
            f"PRICING_GOVERNANCE_READ_FAILED:{exc.__class__.__name__}:{exc}"
        ) from exc


def _required(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    return text


def build_pricing_request_payload(
    *,
    tenant_id: str,
    product_id: str,
    environment: str | None,
    offer_id: str | None,
    plan_id: int | None,
    new_price: int,
    request_id: str,
    suggested_pricing_version: str | None,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "tenant_id": _required(tenant_id, field="tenant_id"),
        "product_id": _required(product_id, field="product_id"),
        "environment": str(environment or "").strip(),
        "offer_id": str(offer_id or "").strip(),
        "plan_id": int(plan_id) if plan_id is not None else None,
        "new_price": int(new_price),
        "request_id": _required(request_id, field="request_id"),
        "suggested_pricing_version": str(suggested_pricing_version or "").strip(),
        "reason": str(reason or "").strip(),
    }


def _request_from_event(event: dict[str, Any]) -> PricingChangeRequest:
    payload = _payload(event)
    raw_plan_id = payload.get("plan_id")
    return PricingChangeRequest(
        request_id=_required(payload.get("request_id"), field="request_id"),
        tenant_id=_required(payload.get("tenant_id"), field="tenant_id"),
        product_id=_required(payload.get("product_id"), field="product_id"),
        environment=str(payload.get("environment") or "").strip(),
        offer_id=str(payload.get("offer_id") or "").strip(),
        plan_id=int(raw_plan_id) if raw_plan_id is not None else None,
        new_price=int(payload.get("new_price")),
        suggested_pricing_version=str(
            payload.get("suggested_pricing_version") or ""
        ).strip(),
        requested_by=_required(event.get("user_id"), field="requested_by"),
        reason=str(payload.get("reason") or "").strip(),
    )


def _same_event_semantics(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        _payload(left) == _payload(right)
        and str(left.get("user_id") or "") == str(right.get("user_id") or "")
    )


def _coalesce_identical_events(
    events: list[dict[str, Any]],
    *,
    conflict_code: str,
) -> dict[str, Any] | None:
    if not events:
        return None
    first = events[0]
    for event in events[1:]:
        if not _same_event_semantics(first, event):
            raise RuntimeError(conflict_code)
    return first


def _assert_terminal_scope_matches_request(
    *,
    request: PricingChangeRequest,
    applied_event: dict[str, Any] | None,
    rejected_event: dict[str, Any] | None,
) -> None:
    conflict = f"PRICING_REQUEST_TERMINAL_CONFLICT:{request.request_id}"
    if applied_event is not None:
        payload = _payload(applied_event)
        raw_plan_id = payload.get("plan_id")
        observed_plan_id = int(raw_plan_id) if raw_plan_id is not None else None
        if (
            str(payload.get("tenant_id") or "").strip() != request.tenant_id
            or str(payload.get("product_id") or "").strip() != request.product_id
            or str(payload.get("environment") or "").strip() != request.environment
            or str(payload.get("offer_id") or "").strip() != request.offer_id
            or observed_plan_id != request.plan_id
            or int(payload.get("new_price") or 0) != request.new_price
            or str(payload.get("requested_by") or "").strip() != request.requested_by
            or (
                request.suggested_pricing_version
                and str(payload.get("pricing_version") or "").strip()
                != request.suggested_pricing_version
            )
        ):
            raise RuntimeError(conflict)
    if rejected_event is not None:
        payload = _payload(rejected_event)
        if (
            str(payload.get("tenant_id") or "").strip() != request.tenant_id
            or str(payload.get("product_id") or "").strip() != request.product_id
            or str(payload.get("request_id") or "").strip() != request.request_id
        ):
            raise RuntimeError(conflict)


def resolve_pricing_request_lifecycle(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> PricingRequestLifecycle:
    tenant = _required(tenant_id, field="tenant_id")
    request_id_text = _required(request_id, field="request_id")

    request_events: list[dict[str, Any]] = []
    applied_events: list[dict[str, Any]] = []
    rejected_events: list[dict[str, Any]] = []
    for event in _events(event_log):
        payload = _payload(event)
        if str(payload.get("tenant_id") or "").strip() != tenant:
            continue
        if str(payload.get("request_id") or "").strip() != request_id_text:
            continue
        event_type = _event_type(event)
        if event_type == REQUEST_EVENT:
            request_events.append(event)
        elif event_type == APPLIED_EVENT:
            applied_events.append(event)
        elif event_type == REJECTED_EVENT:
            rejected_events.append(event)

    request_event = _coalesce_identical_events(
        request_events,
        conflict_code=(
            f"PRICING_CHANGE_REQUEST_ID_NOT_UNIQUE:{tenant}:{request_id_text}"
        ),
    )
    if request_event is None:
        raise RuntimeError(
            f"PRICING_CHANGE_REQUEST_NOT_FOUND:{tenant}:{request_id_text}"
        )

    terminal_conflict = f"PRICING_REQUEST_TERMINAL_CONFLICT:{request_id_text}"
    applied_event = _coalesce_identical_events(
        applied_events,
        conflict_code=terminal_conflict,
    )
    rejected_event = _coalesce_identical_events(
        rejected_events,
        conflict_code=terminal_conflict,
    )
    if applied_event is not None and rejected_event is not None:
        raise RuntimeError(terminal_conflict)

    request = _request_from_event(request_event)
    _assert_terminal_scope_matches_request(
        request=request,
        applied_event=applied_event,
        rejected_event=rejected_event,
    )
    return PricingRequestLifecycle(
        request_event=request_event,
        request=request,
        applied_event=applied_event,
        rejected_event=rejected_event,
    )


def resolve_pricing_change_request(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> PricingChangeRequest:
    return resolve_pricing_request_lifecycle(
        event_log,
        tenant_id=tenant_id,
        request_id=request_id,
    ).request


def assert_pricing_request_id_available(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> None:
    tenant = _required(tenant_id, field="tenant_id")
    request = _required(request_id, field="request_id")
    for event in _events(event_log):
        if _event_type(event) != REQUEST_EVENT:
            continue
        payload = _payload(event)
        if str(payload.get("tenant_id") or "").strip() != tenant:
            continue
        if str(payload.get("request_id") or "").strip() == request:
            raise RuntimeError(
                f"PRICING_CHANGE_REQUEST_ID_ALREADY_EXISTS:{tenant}:{request}"
            )


def assert_pricing_request_open(
    event_log: Any,
    *,
    tenant_id: str,
    request_id: str,
) -> None:
    lifecycle = resolve_pricing_request_lifecycle(
        event_log,
        tenant_id=tenant_id,
        request_id=request_id,
    )
    if lifecycle.applied_event is not None or lifecycle.rejected_event is not None:
        raise RuntimeError(
            f"PRICING_CHANGE_REQUEST_ALREADY_RESOLVED:{lifecycle.request_id}"
        )


def assert_pricing_request_matches(
    lifecycle: PricingRequestLifecycle,
    *,
    product_id: str,
    environment: str | None,
    offer_id: str | None,
    plan_id: int | None,
    new_price: int,
    pricing_version: str | None = None,
) -> None:
    request = lifecycle.request
    mismatches: list[str] = []
    if str(product_id).strip() != request.product_id:
        mismatches.append("product_id")
    if str(environment or "").strip() != request.environment:
        mismatches.append("environment")
    if str(offer_id or "").strip() != request.offer_id:
        mismatches.append("offer_id")
    if plan_id != request.plan_id:
        mismatches.append("plan_id")
    if int(new_price) != request.new_price:
        mismatches.append("new_price")
    if (
        request.suggested_pricing_version
        and pricing_version is not None
        and str(pricing_version).strip() != request.suggested_pricing_version
    ):
        mismatches.append("pricing_version")
    if mismatches:
        raise RuntimeError(
            "PRICING_CHANGE_REQUEST_MISMATCH:"
            + request.request_id
            + ":"
            + ",".join(sorted(mismatches))
        )


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
    lifecycle = resolve_pricing_request_lifecycle(
        event_log,
        tenant_id=tenant_id,
        request_id=request_id,
    )
    if lifecycle.applied_event is not None or lifecycle.rejected_event is not None:
        raise RuntimeError(
            f"PRICING_CHANGE_REQUEST_ALREADY_RESOLVED:{lifecycle.request_id}"
        )
    assert_pricing_request_matches(
        lifecycle,
        product_id=product_id,
        environment=environment,
        offer_id=offer_id,
        plan_id=plan_id,
        new_price=new_price,
        pricing_version=pricing_version,
    )
    return lifecycle.request


def assert_pricing_approval_allowed(
    lifecycle: PricingRequestLifecycle,
    *,
    admin_id: str,
) -> None:
    if lifecycle.rejected_event is not None:
        raise RuntimeError(f"PRICING_REQUEST_REJECTED:{lifecycle.request_id}")
    if (
        lifecycle.requested_by == str(admin_id).strip()
        and not env_bool("ALLOW_SELF_APPROVE", False)
    ):
        raise RuntimeError("SELF_APPROVAL_FORBIDDEN")


def assert_pricing_rejection_allowed(lifecycle: PricingRequestLifecycle) -> None:
    if lifecycle.applied_event is not None:
        raise RuntimeError(
            f"PRICING_REQUEST_ALREADY_APPLIED:{lifecycle.request_id}"
        )


def pricing_event_evidence(
    *,
    code: str,
    event: dict[str, Any],
    fallback_ref: str,
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "").strip()
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [event_id or str(fallback_ref)],
        "confidence": 1.0,
        "payload": _payload(event),
    }


__all__ = [
    "APPLIED_EVENT",
    "PricingChangeRequest",
    "PricingRequestLifecycle",
    "REJECTED_EVENT",
    "REQUEST_EVENT",
    "TERMINAL_EVENTS",
    "assert_pricing_approval_allowed",
    "assert_pricing_rejection_allowed",
    "assert_pricing_request_id_available",
    "assert_pricing_request_matches",
    "assert_pricing_request_open",
    "build_pricing_request_payload",
    "pricing_event_evidence",
    "resolve_pricing_change_request",
    "resolve_pricing_request_lifecycle",
    "validate_pricing_apply_against_request",
]
