from __future__ import annotations

from typing import Any

from runtime.observability.error_handling import swallow

CANON_ADMIN_PRICING_SUPPORT = True


def build_pricing_change_payload(
    *,
    request_id: str = "",
    plan_id: int | None = None,
    new_price: int | None = None,
    pricing_version: str = "",
    requested_by: str = "",
    reason: str = "",
    suggested_pricing_version: str = "",
    rejected_by: str = "",
    plans_path: str = "",
    override_path: str = "",
    override_persisted: bool = False,
) -> dict[str, Any]:
    """Build pricing audit metadata without storage or execution authority."""

    payload: dict[str, Any] = {"request_id": str(request_id or "")}
    if plan_id is not None:
        payload["plan_id"] = int(plan_id)
    if new_price is not None:
        payload["new_price"] = int(new_price)
    if pricing_version:
        payload["pricing_version"] = str(pricing_version)
    if requested_by:
        payload["requested_by"] = str(requested_by)
    if reason:
        payload["reason"] = str(reason)
    if suggested_pricing_version:
        payload["suggested_pricing_version"] = str(suggested_pricing_version)
    if rejected_by:
        payload["rejected_by"] = str(rejected_by)
    if plans_path:
        payload["plans_path"] = str(plans_path)
    if override_path:
        payload["override_path"] = str(override_path)
    payload["override_persisted"] = bool(override_persisted)
    return payload


def emit_pricing_change_event(
    event_log: Any,
    *,
    event_type: str,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    payload: dict[str, Any],
) -> None:
    event_log.emit(
        event_type=str(event_type),
        source="pricing.governance",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=dict(payload),
    )


def emit_pricing_reset(
    event_log: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
) -> None:
    try:
        event_log.emit(
            event_type="user_setting_set",
            source="pricing.governance",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"key": "admin:pricing_session", "value": {}},
        )
    except Exception:
        swallow(__name__, "admin_pricing_support.emit_pricing_reset")


__all__ = [
    "CANON_ADMIN_PRICING_SUPPORT",
    "build_pricing_change_payload",
    "emit_pricing_change_event",
    "emit_pricing_reset",
]
