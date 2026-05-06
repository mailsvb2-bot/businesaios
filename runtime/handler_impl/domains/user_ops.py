from __future__ import annotations

from runtime.handler_impl.core.payloads import (
    clamp_int,
    optional_dict,
    optional_str,
    require_mapping,
    required_str,
)


def handle_answer_callback(payload, effects, env):
    payload = require_mapping(payload or {})
    user_id = required_str({"user_id": payload.get("user_id") or (env.decision.payload or {}).get("user_id") or "unknown"}, "user_id")
    callback_query_id = required_str(payload, "callback_query_id")
    return effects.answer_callback_query(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=user_id,
        callback_query_id=callback_query_id,
        text=optional_str(payload, "text"),
        show_alert=bool(payload.get("show_alert", False)),
    )


def handle_send_audio(payload, effects, env):
    payload = require_mapping(payload)
    return effects.send_audio(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        path=required_str(payload, "path"),
        kind=str(payload.get("kind") or "voice"),
        caption=optional_str(payload, "caption"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )


def handle_send_weather(payload, effects, env):
    payload = require_mapping(payload)
    return effects.send_weather(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
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


def handle_log_mood(payload, effects, env):
    payload = require_mapping(payload)
    score = clamp_int(int(payload.get("score", 0)), min_value=0, max_value=10)
    return effects.log_mood(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=required_str(payload, "user_id"),
        score=score,
        note=optional_str(payload, "note"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
    )
