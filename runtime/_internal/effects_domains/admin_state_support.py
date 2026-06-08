from __future__ import annotations

from typing import Any, Optional

from runtime._internal.effects_domains.admin_pricing_effects import (
    apply_pricing_change_effect,
    build_pricing_change_payload,
    emit_pricing_change_event,
    emit_pricing_reset,
    reject_pricing_change_effect,
    request_pricing_change_effect,
)
from runtime.observability.error_handling import swallow


def answer_callback_if_needed(owner: Any, *, channel: str, callback_query_id: str | None) -> None:
    if channel != "telegram" or not isinstance(callback_query_id, str) or not callback_query_id.strip():
        return
    try:
        owner._telegram_answer_callback(callback_query_id.strip())  # type: ignore[attr-defined]
    except Exception:
        swallow(__name__, "runtime/_internal/effects_domains/admin_state_support.py")


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
) -> None:
    event_log.emit(
        event_type=event_type,
        source="admin_state",
        user_id=str(admin_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "target_user_id": str(target_user_id),
            str(field_name): str(field_value),
            "enabled": bool(enabled),
        },
    )



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
        return {"ok": True}
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
        raise
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
) -> Any:
    answer_callback_if_needed(owner, channel=channel, callback_query_id=callback_query_id)
    emit_toggle_event(
        event_log,
        event_type=f"admin_{field_name}_set",
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        admin_id=str(admin_id),
        target_user_id=str(target_user_id),
        field_name=str(field_name),
        field_value=str(field_value),
        enabled=bool(enabled),
    )
    return send_optional_notification(
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
