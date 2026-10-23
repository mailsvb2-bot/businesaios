from __future__ import annotations

from runtime.handler_impl.core.payloads import (
    clamp_int,
    optional_dict,
    optional_str,
    require_mapping,
    required_str,
)
from runtime.handlers.delivery_contract import delivery_kwargs


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


def handle_send_audio(payload, effects, env):
    payload = require_mapping(payload)
    return effects.send_audio(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        business_id=optional_str(payload, "business_id") or "",
        user_id=required_str(payload, "user_id"),
        path=required_str(payload, "path"),
        kind=str(payload.get("kind") or "voice"),
        caption=optional_str(payload, "caption"),
        callback_query_id=optional_str(payload, "callback_query_id"),
        channel=str(payload.get("channel") or "telegram"),
    )


def handle_send_weather(payload, effects, env):
    payload = require_mapping(payload)
    return effects.send_weather(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        user_id=required_str(payload, "user_id"),
        city=required_str(payload, "city"),
        **delivery_kwargs(payload),
    )


def handle_set_user_setting(payload, effects, env):
    payload = require_mapping(payload)
    return effects.set_user_setting(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        user_id=required_str(payload, "user_id"),
        key=required_str(payload, "key"),
        value=payload.get("value"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
        **delivery_kwargs(payload),
    )


def handle_log_mood(payload, effects, env):
    payload = require_mapping(payload)
    score = clamp_int(int(payload.get("score", 0)), min_value=0, max_value=10)
    return effects.log_mood(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=required_str(payload, "tenant_id"),
        user_id=required_str(payload, "user_id"),
        score=score,
        note=optional_str(payload, "note"),
        notify_text=optional_str(payload, "notify_text"),
        notify_reply_markup=optional_dict(payload, "notify_reply_markup"),
        callback_query_id=optional_str(payload, "callback_query_id"),
        channel=str(payload.get("channel") or "telegram"),
        channel_policy=optional_dict(payload, "channel_policy"),
    )


def handle_privacy_export(payload, effects, env, *, event_store):
    """Self-service personal-data export: the requester sees only their own scoped events."""
    from collections import Counter

    from core.privacy.data_rights import DataExportRequest, DataRightsService
    from runtime.platform.privacy.event_store_data_source import EventStoreUserDataSource

    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    try:
        service = DataRightsService(sources={"events": EventStoreUserDataSource(event_store)})
        items = service.export_user(DataExportRequest(tenant_id=tenant_id, user_id=user_id))["sources"]["events"]["items"]
        types = Counter(str((i if isinstance(i, dict) else vars(i)).get("event_type") or "?") for i in items)
        lines = [f"• {name}: {count}" for name, count in types.most_common(15)]
        text = "🔐 Ваши данные\n\n" + f"Записей: {len(items)}\n" + ("\n".join(lines) or "Записей нет.")
        track, ok = "privacy_export@v1", True
    except Exception as exc:
        text, track, ok = "🔐 Не удалось собрать выгрузку данных. Попробуйте позже.", "privacy_export_failed@v1", False
        types, items = {"error": exc.__class__.__name__}, []
    delivery = effects.send_message(
        decision_id=env.decision.decision_id, correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id, user_id=user_id, text=text, reply_markup=None, track_event_type=track,
        track_payload={"tenant_id": tenant_id, "user_id": user_id, "records": len(items), "types": dict(types)},
        **delivery_kwargs(body),
    )
    delivered = bool(delivery.get("ok")) if isinstance(delivery, dict) else bool(delivery)
    return {"ok": bool(ok and delivered), "status": "verified" if ok and delivered else "failed", "delivery": delivery}
