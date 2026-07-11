from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions.telegram.messaging_parts import (
    build_outbound_message,
    build_single_sender,
    execute_delivery_path,
    track_business_event,
    track_delivery,
)


def _delivery_external_refs(meta: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    receipt = meta.get("receipt") if isinstance(meta.get("receipt"), Mapping) else {}
    for value in (
        meta.get("external_id"),
        receipt.get("external_id"),
        meta.get("delivery_key"),
    ):
        text = str(value or "").strip()
        if text and text not in refs:
            refs.append(text)
    return refs


def _delivery_evidence(*, ok: bool, meta: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(meta or {})
    finalized = bool(payload.get("delivery_finalized", False))
    phase = str(payload.get("delivery_phase") or "").strip().casefold()
    mode = str(payload.get("mode") or "").strip().casefold()
    accepted_for_delivery = bool(ok) and (
        phase == "accepted_for_delivery"
        or mode in {"queued", "accepted"}
        or (bool(payload.get("dedup")) and not finalized)
    )

    if finalized:
        source = "connector"
        status = "verified"
        confidence = 1.0
    elif accepted_for_delivery:
        source = "ledger"
        status = "observed"
        confidence = 1.0
    else:
        source = "connector"
        status = "failed" if not ok else "observed"
        confidence = 0.0 if not ok else 1.0

    return {
        "source": source,
        "action_type": str(EffectActionType.TELEGRAM_SEND_MESSAGE),
        "status": status,
        "summary": phase or mode or status,
        "external_refs": _delivery_external_refs(payload),
        "confidence": confidence,
        "payload": {
            "delivery_phase": phase or None,
            "delivery_finalized": finalized,
            "mode": mode or None,
            "dedup": bool(payload.get("dedup", False)),
        },
    }


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
    return {
        "ok": bool(ok),
        "meta": meta,
        "evidence": _delivery_evidence(ok=bool(ok), meta=meta),
    }


__all__ = ["send_message_effect"]
