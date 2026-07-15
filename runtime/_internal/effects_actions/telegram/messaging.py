from __future__ import annotations

from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions.telegram.delivery_evidence import build_delivery_evidence
from runtime._internal.effects_actions.telegram.messaging_parts import (
    build_outbound_message,
    build_single_sender,
    execute_delivery_path,
    track_business_event,
    track_delivery,
)


def send_message_effect(
    self,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    text: str,
    tenant_id: str = "",
    reply_markup: dict | None = None,
    callback_query_id: str | None = None,
    track_event_type: str | None = None,
    track_payload: dict | None = None,
    channel: str = "telegram",
    priority: Any = "normal",
    critical: bool = True,
    channel_policy: dict | None = None,
) -> Any:
    msg = build_outbound_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        text=text,
        tenant_id=tenant_id,
        reply_markup=reply_markup,
        callback_query_id=callback_query_id,
        track_event_type=track_event_type,
        track_payload=track_payload,
        channel=channel,
        priority=priority,
        critical=critical,
    )
    ok, meta = execute_delivery_path(
        self,
        msg=msg,
        channel_policy=channel_policy,
        send_once=build_single_sender(self),
    )
    track_delivery(
        self,
        user_id=msg.user_id,
        decision_id=msg.decision_id,
        correlation_id=msg.correlation_id,
        channel=str((meta.get("policy") or {}).get("selected_channel") or msg.channel),
        text=msg.text,
        ok=bool(ok),
        meta=meta,
    )
    track_business_event(
        self,
        user_id=msg.user_id,
        decision_id=msg.decision_id,
        correlation_id=msg.correlation_id,
        track_event_type=msg.track_event_type,
        track_payload=msg.track_payload,
    )
    evidence_action_type = (
        str(EffectActionType.TELEGRAM_SEND_MESSAGE)
        if msg.channel == "telegram"
        else "messaging.send_message"
    )
    return {
        "ok": bool(ok),
        "meta": meta,
        "evidence": build_delivery_evidence(
            ok=bool(ok),
            meta=meta,
            action_type=evidence_action_type,
        ),
    }


__all__ = ["send_message_effect"]

