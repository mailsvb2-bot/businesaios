from __future__ import annotations

from typing import Any

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
    admin_id: str,
    target_user_id: str,
    field_name: str,
    field_value: str,
    enabled: bool,
) -> dict[str, Any]:
    payload = {
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
    admin_id: str,
    notify_text: str | None,
    notify_reply_markup: dict[str, Any] | None,
    callback_query_id: str | None,
    channel: str,
    event_log: Any | None = None,
) -> Any:
    if not isinstance(notify_text, str) or not notify_text.strip():
        return None
    try:
        result = owner.send_message(  # type: ignore[attr-defined]
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            user_id=str(admin_id),
            text=str(notify_text)[:3500],
            reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
            callback_query_id=str(callback_query_id) if callback_query_id else None,
            channel=str(channel),
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
    admin_id: str,
    target_user_id: str,
    field_name: str,
    field_value: str,
    enabled: bool,
    notify_text: str | None,
    notify_reply_markup: dict[str, Any] | None,
    callback_query_id: str | None,
    channel: str,
    event_log: Any,
) -> dict[str, Any]:
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
        admin_id=str(admin_id),
        notify_text=notify_text,
        notify_reply_markup=notify_reply_markup,
        callback_query_id=callback_query_id,
        channel=channel,
        event_log=event_log,
    )
    external_ref = f"{event_type}:{decision_id}:{target_user_id}:{field_value}:{int(bool(enabled))}"
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

    validate_pricing_change(
        admin_id=str(admin_id),
        requested_by=requested_by,
        pricing_version=str(pricing_version),
    )
    result = execute_plan_price_update(
        plan_id=int(plan_id),
        new_price=int(new_price),
        pricing_version=str(pricing_version),
    )
    event_log = getattr(owner, "event_log", None)
    if event_log is None:
        raise RuntimeError("PRICING_EVENT_LOG_REQUIRED")
    payload = {
        "plan_id": int(plan_id),
        "new_price": int(new_price),
        "pricing_version": str(pricing_version),
        "request_id": str(request_id or ""),
        "requested_by": str(requested_by or ""),
        "reason": str(reason or ""),
        "result": dict(result),
    }
    event_log.emit(
        event_type="admin_pricing_change_applied",
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    return {
        "ok": True,
        "status": "verified",
        "result": dict(result),
        "router_evidence": _ledger_evidence(
            code="pricing_change_recorded",
            external_ref=f"pricing:{pricing_version}:plan:{int(plan_id)}",
            payload=payload,
        ),
    }


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
    event_log = getattr(owner, "event_log", None)
    payload = {
        "plan_id": int(plan_id),
        "new_price": int(new_price),
        "request_id": str(request_id),
        "suggested_pricing_version": str(suggested_pricing_version or ""),
        "reason": str(reason or ""),
    }
    if event_log is not None:
        event_log.emit(
            event_type="admin_pricing_change_requested",
            source="admin_state",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
    return {"ok": True, "request": payload}


def reject_pricing_change_effect(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    admin_id: str,
    request_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    event_log = getattr(owner, "event_log", None)
    payload = {
        "request_id": str(request_id),
        "reason": str(reason or ""),
    }
    if event_log is not None:
        event_log.emit(
            event_type="admin_pricing_change_rejected",
            source="admin_state",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
    return {"ok": True, "rejection": payload}
