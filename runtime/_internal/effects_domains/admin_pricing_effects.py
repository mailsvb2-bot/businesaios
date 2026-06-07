from __future__ import annotations

from typing import Any

from runtime._internal.effects_domains.admin_state_helpers import emit_user_setting_reset


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
        event_type=event_type,
        source="pricing.governance",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=dict(payload),
    )


def emit_pricing_reset(event_log: Any, *, decision_id: str, correlation_id: str, admin_id: str) -> None:
    emit_user_setting_reset(
        event_log,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
    )


def apply_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    plan_id: int,
    new_price: int,
    pricing_version: str,
    request_id: str | None = None,
    requested_by: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    from runtime._internal.effects_domains.admin_pricing import (
        execute_plan_price_update,
        validate_pricing_change,
    )

    validate_pricing_change(admin_id=admin_id, requested_by=requested_by, pricing_version=pricing_version)
    result = execute_plan_price_update(plan_id=plan_id, new_price=new_price, pricing_version=pricing_version)
    pid = result["plan_id"]
    price = result["new_price"]
    version = result["pricing_version"]
    plans_path = result.get("plans_path", "")
    override_path = result.get("override_path", "")
    override_persisted = bool(result.get("override_persisted", False))

    emit_pricing_change_event(
        owner.event_log,
        event_type="pricing_change_applied",
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
        payload=build_pricing_change_payload(
            request_id=str(request_id or ""),
            plan_id=pid,
            new_price=price,
            pricing_version=version,
            requested_by=str(requested_by or ""),
            reason=str(reason or ""),
            plans_path=str(plans_path),
            override_path=str(override_path),
            override_persisted=override_persisted,
        ),
    )
    emit_pricing_reset(
        owner.event_log,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
    )
    return {"ok": True, "plan_id": pid, "new_price": price, "pricing_version": version}


def request_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    plan_id: int,
    new_price: int,
    request_id: str,
    suggested_pricing_version: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    pid = int(plan_id)
    price = int(new_price)
    rid = str(request_id)
    sv = str(suggested_pricing_version or "").strip()
    rsn = str(reason or "").strip()

    emit_pricing_change_event(
        owner.event_log,
        event_type="pricing_change_requested",
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
        payload=build_pricing_change_payload(
            request_id=rid,
            plan_id=pid,
            new_price=price,
            suggested_pricing_version=sv,
            reason=rsn,
            requested_by=str(admin_id),
        ),
    )
    emit_pricing_reset(
        owner.event_log,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
    )
    return {"ok": True, "request_id": rid, "plan_id": pid, "new_price": price}


def reject_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    request_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    rid = str(request_id)
    rsn = str(reason or "").strip()
    emit_pricing_change_event(
        owner.event_log,
        event_type="pricing_change_rejected",
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
        payload=build_pricing_change_payload(
            request_id=rid,
            reason=rsn,
            rejected_by=str(admin_id),
        ),
    )
    return {"ok": True, "request_id": rid}


__all__ = [
    "apply_pricing_change_effect",
    "build_pricing_change_payload",
    "emit_pricing_change_event",
    "emit_pricing_reset",
    "reject_pricing_change_effect",
    "request_pricing_change_effect",
]
