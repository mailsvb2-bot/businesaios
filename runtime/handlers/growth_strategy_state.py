from __future__ import annotations

from typing import Any

from runtime.growth import GrowthStrategyService
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME_ACCEPT = "growth_strategy_accept@v1"
ACTION_NAME_REJECT = "growth_strategy_reject@v1"

def handle_growth_strategy_accept(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    return _handle(payload, effects, env, event_store=event_store, state="accept")


def handle_growth_strategy_reject(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    return _handle(payload, effects, env, event_store=event_store, state="reject")


def _handle(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any, state: str) -> Any:
    p = payload or {}
    tenant_id = str(p.get("tenant_id") or getattr(env, "tenant_id", "") or "")
    user_id = str(p.get("user_id") or "")
    decision_id = str(getattr(env, "decision", None).decision_id if getattr(env, "decision", None) else p.get("decision_id") or "")
    correlation_id = str(getattr(env, "decision", None).correlation_id if getattr(env, "decision", None) else p.get("correlation_id") or "")
    hid = str(p.get("hypothesis_id") or "")

    svc = GrowthStrategyService(event_store=event_store, llm=None)
    if state == "accept":
        svc.accept_hypothesis(tenant_id=tenant_id, user_id=user_id, decision_id=decision_id, correlation_id=correlation_id, hypothesis_id=hid)
        text = f"✅ Принято: {hid}"
        action = ACTION_NAME_ACCEPT
    else:
        svc.reject_hypothesis(tenant_id=tenant_id, user_id=user_id, decision_id=decision_id, correlation_id=correlation_id, hypothesis_id=hid)
        text = f"❌ Отклонено: {hid}"
        action = ACTION_NAME_REJECT

    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        text=text,
        reply_markup={"inline_keyboard": [[{"text": "📋 Backlog", "callback_data": "growth:backlog"}]]},
        callback_query_id=p.get("callback_query_id"),
        critical=False,
        track_event_type=action,
        track_payload={"tenant_id": tenant_id, "hypothesis_id": hid},
    )
