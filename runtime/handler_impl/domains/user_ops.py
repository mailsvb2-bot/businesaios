from __future__ import annotations

from runtime.handler_impl.core.payloads import (
    optional_dict,
    optional_str,
    require_mapping,
    required_str,
)


def handle_answer_callback(payload, effects, env):
    payload = require_mapping(payload or {})
    user_id = required_str(
        {"user_id": payload.get("user_id") or (env.decision.payload or {}).get("user_id") or "unknown"},
        "user_id",
    )
    callback_query_id = required_str(payload, "callback_query_id")
    return effects.answer_callback_query(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        callback_query_id=callback_query_id,
        text=optional_str(payload, "text"),
        show_alert=bool(payload.get("show_alert", False)),
    )


def handle_send_weather(payload, effects, env):
    payload = require_mapping(payload)
    return effects.send_weather(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        user_id=required_str(payload, "user_id"),
        city=required_str(payload, "city"),
    )


def handle_set_user_setting(payload, effects, env):
    payload = require_mapping(payload)
    return effects.set_user_setting(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        key=required_str(payload, "key"),
        value=payload.get("value"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )
