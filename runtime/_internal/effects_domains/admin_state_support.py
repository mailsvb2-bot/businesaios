from __future__ import annotations

from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow


def _ledger_evidence(*, code: str, external_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [str(external_ref)],
        "confidence": 1.0,
        "payload": dict(payload),
    }


def _emitted_event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id") or "").strip()
    return str(getattr(event, "event_id", "") or "").strip()


def answer_callback_if_needed(
    owner: Any,
    *,
    channel: str,
    callback_query_id: str | None,
    user_id: str,
    decision_id: str,
    correlation_id: str,
) -> None:
    if channel != "telegram" or not isinstance(callback_query_id, str) or not callback_query_id.strip():
        return
    try:
        owner._telegram_answer_callback(  # type: ignore[attr-defined]
            callback_query_id.strip(),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
        )
    except Exception:
        swallow(__name__, "admin_state.answer_callback")


def emit_toggle_event(
    event_log: Any,
    *,
    event_type: str,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    admin_id: str,
    target_user_id: str,
    field_name: str,
    field_value: str,
    enabled: bool,
) -> dict[str, Any]:
    payload = {
        "tenant_id": str(tenant_id),
        "target_user_id": str(target_user_id),
        str(field_name): str(field_value),
        "enabled": bool(enabled),
    }
    event_log.emit(
        event_type=event_type,
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    return payload


def emit_admin_notification_event(
    event_log: Any,
    *,
    event_type: str,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    channel: str,
    callback_query_id: str | None,
    text: str,
    error: str = "",
) -> None:
    payload = {
        "channel": str(channel),
        "has_callback_query": bool(callback_query_id),
        "text_len": len(str(text or "")),
    }
    if error:
        payload["error"] = str(error)
    event_log.emit(
        event_type=str(event_type),
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )


def send_optional_notification(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    admin_id: str,
    notify_text: str | None,
    notify_reply_markup: dict[str, Any] | None,
    callback_query_id: str | None,
    channel: str,
    channel_policy: dict[str, Any] | None,
    event_log: Any | None = None,
) -> Any:
    if not isinstance(notify_text, str) or not notify_text.strip():
        return None
    try:
        result = owner.send_message(  # type: ignore[attr-defined]
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=str(tenant_id),
            user_id=str(admin_id),
            text=str(notify_text)[:3500],
            reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
            callback_query_id=str(callback_query_id) if callback_query_id else None,
            channel=str(channel),
            channel_policy=(
                dict(channel_policy)
                if isinstance(channel_policy, dict)
                else None
            ),
        )
    except Exception as exc:
        if event_log is not None:
            emit_admin_notification_event(
                event_log,
                event_type="admin_notification_failed",
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                admin_id=str(admin_id),
                channel=str(channel),
                callback_query_id=callback_query_id,
                text=str(notify_text),
                error=exc.__class__.__name__,
            )
        return {"ok": False, "error": exc.__class__.__name__}
    if event_log is not None:
        emit_admin_notification_event(
            event_log,
            event_type="admin_notification_sent",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            admin_id=str(admin_id),
            channel=str(channel),
            callback_query_id=callback_query_id,
            text=str(notify_text),
        )
    return result


def perform_admin_toggle(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    admin_id: str,
    target_user_id: str,
    field_name: str,
    field_value: str,
    enabled: bool,
    notify_text: str | None,
    notify_reply_markup: dict[str, Any] | None,
    callback_query_id: str | None,
    channel: str,
    channel_policy: dict[str, Any] | None,
    event_log: Any,
) -> dict[str, Any]:
    tenant = assert_event_log_tenant(
        event_log,
        tenant_id=str(tenant_id),
        operation=f"admin_{field_name}_set",
    )
    answer_callback_if_needed(
        owner,
        channel=channel,
        callback_query_id=callback_query_id,
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
    )
    event_type = f"admin_{field_name}_set"
    payload = emit_toggle_event(
        event_log,
        event_type=event_type,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        tenant_id=tenant,
        admin_id=str(admin_id),
        target_user_id=str(target_user_id),
        field_name=str(field_name),
        field_value=str(field_value),
        enabled=bool(enabled),
    )
    notification = send_optional_notification(
        owner,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        tenant_id=tenant,
        admin_id=str(admin_id),
        notify_text=notify_text,
        notify_reply_markup=notify_reply_markup,
        callback_query_id=callback_query_id,
        channel=channel,
        channel_policy=channel_policy,
        event_log=event_log,
    )
    external_ref = f"{event_type}:{tenant}:{decision_id}:{target_user_id}:{field_value}:{int(bool(enabled))}"
    return {
        "ok": True,
        "status": "verified",
        "change": payload,
        "notification": notification,
        "router_evidence": _ledger_evidence(
            code=f"{field_name}_change_recorded",
            external_ref=external_ref,
            payload=payload,
        ),
    }


def apply_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    tenant_id: str,
    product_id: str,
    new_price: int,
    pricing_version: str,
    environment: str | None = None,
    offer_id: str | None = None,
    plan_id: int | None = None,
    request_id: str | None = None,
    requested_by: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    from runtime._internal.effects_domains.admin_pricing import (
        prepare_offer_price_update,
        validate_pricing_change,
    )

    validate_pricing_change(
        admin_id=str(admin_id),
        requested_by=requested_by,
        pricing_version=str(pricing_version),
    )
    event_log = getattr(owner, "event_log", None)
    if event_log is None:
        raise RuntimeError("PRICING_EVENT_LOG_REQUIRED")
    tenant = assert_event_log_tenant(
        event_log,
        tenant_id=str(tenant_id),
        operation="apply_pricing_change",
    )

    transaction = prepare_offer_price_update(
        tenant_id=tenant,
        product_id=str(product_id),
        environment=environment,
        offer_id=offer_id,
        plan_id=plan_id,
        new_price=int(new_price),
        pricing_version=str(pricing_version),
    )
    event: Any = None
    try:
        result = transaction.apply()
        payload = {
            **dict(result),
            "request_id": str(request_id or ""),
            "requested_by": str(requested_by or ""),
            "reason": str(reason or ""),
        }
        event = event_log.emit(
            event_type="admin_pricing_change_applied",
            source="admin_state",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
    except Exception:
        if transaction.applied:
            transaction.rollback()
        transaction.finalize()
        raise
    transaction.finalize()

    catalog_id = str(result.get("catalog_id") or "")
    resolved_offer_id = str(result.get("offer_id") or "")
    fallback_ref = (
        f"pricing:{catalog_id}:offer:{resolved_offer_id}:version:{pricing_version}"
    )
    return {
        "ok": True,
        "status": "verified",
        "result": dict(result),
        "router_evidence": _ledger_evidence(
            code="pricing_change_recorded",
            external_ref=_emitted_event_id(event) or fallback_ref,
            payload=payload,
        ),
    }


def request_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    tenant_id: str,
    product_id: str,
    new_price: int,
    request_id: str,
    environment: str | None = None,
    offer_id: str | None = None,
    plan_id: int | None = None,
    suggested_pricing_version: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    event_log = getattr(owner, "event_log", None)
    if event_log is None:
        raise RuntimeError("PRICING_EVENT_LOG_REQUIRED")
    tenant = assert_event_log_tenant(
        event_log,
        tenant_id=str(tenant_id),
        operation="request_pricing_change",
    )
    payload = {
        "tenant_id": tenant,
        "product_id": str(product_id),
        "environment": str(environment or ""),
        "offer_id": str(offer_id or ""),
        "plan_id": int(plan_id) if plan_id is not None else None,
        "new_price": int(new_price),
        "request_id": str(request_id),
        "suggested_pricing_version": str(suggested_pricing_version or ""),
        "reason": str(reason or ""),
    }
    event = event_log.emit(
        event_type="admin_pricing_change_requested",
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    fallback_ref = f"pricing-request:{tenant}:{product_id}:{request_id}"
    return {
        "ok": True,
        "status": "verified",
        "request": payload,
        "router_evidence": _ledger_evidence(
            code="pricing_change_request_recorded",
            external_ref=_emitted_event_id(event) or fallback_ref,
            payload=payload,
        ),
    }


def reject_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    tenant_id: str,
    request_id: str,
    product_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    event_log = getattr(owner, "event_log", None)
    if event_log is None:
        raise RuntimeError("PRICING_EVENT_LOG_REQUIRED")
    tenant = assert_event_log_tenant(
        event_log,
        tenant_id=str(tenant_id),
        operation="reject_pricing_change",
    )
    payload = {
        "tenant_id": tenant,
        "product_id": str(product_id or ""),
        "request_id": str(request_id),
        "reason": str(reason or ""),
    }
    event = event_log.emit(
        event_type="admin_pricing_change_rejected",
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    fallback_ref = (
        f"pricing-rejection:{tenant}:{product_id or '-'}:{request_id}"
    )
    return {
        "ok": True,
        "status": "verified",
        "rejection": payload,
        "router_evidence": _ledger_evidence(
            code="pricing_change_rejection_recorded",
            external_ref=_emitted_event_id(event) or fallback_ref,
            payload=payload,
        ),
    }
