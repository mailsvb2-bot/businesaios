from __future__ import annotations

import logging
from typing import Any

from core.retention.offer_steps import render_offer_payload, should_allow_offer
from core.tenancy.normalization import normalize_tenant_id

log = logging.getLogger(__name__)


def make_telemetry_step(*, decision: Any, user_id: str) -> dict[str, Any]:
    return {
        "action": "track_event@v1",
        "user_id": user_id,
        "event_type": "retention_decided",
        "payload": {
            "tenant_id": decision.tenant_id,
            "day_key": decision.day_key,
            "day_index": decision.day_index,
            "hazard": decision.hazard,
            "readiness": decision.readiness,
            "offer_arm": decision.offer_arm or "NONE",
            "suppressed": bool(decision.suppressed),
            "reason": decision.reason,
        },
    }


def offer_allowed(*, offer_engine: Any, cooldown_store: Any, state: Any, tenant_id: str, user_id: str, offer_id: str) -> bool:
    return should_allow_offer(
        offer_engine=offer_engine,
        cooldown_store=cooldown_store,
        state=state,
        tenant_id=tenant_id,
        user_id=user_id,
        offer_id=offer_id,
    )


def render_offer_step(*, offer_engine: Any, state: Any, decision: Any, user_id: str, max_band: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    tenant_id = normalize_tenant_id(getattr(state, "tenant_id", None), fallback=str(decision.tenant_id or "").strip())
    offer_text, offer_variant, offer_meta, price_for_render = render_offer_payload(
        offer_engine=offer_engine,
        state=state,
        tenant_id=tenant_id,
        user_id=user_id,
        offer_id=str(decision.offer_arm),
        price_rub=int(decision.offer_price_rub),
        day_key=str(decision.day_key),
        day_index=int(decision.day_index),
        max_band=max_band,
        default_logger=log,
    )
    chat_id = None
    if getattr(state, "telegram_update", None):
        chat_id = state.telegram_update.get("message", {}).get("chat", {}).get("id")
    step = {
        "action": "send_marketing_offer@v1",
        "tenant_id": str(decision.tenant_id),
        "user_id": user_id,
        "chat_id": chat_id,
        "locale": str(getattr(state, "locale", None) or getattr(state, "user_locale", None) or "ru"),
        "channel": "telegram",
        "features": (getattr(state, "features", None) if isinstance(getattr(state, "features", None), dict) else {}),
        "offer": {
            "id": str(decision.offer_arm),
            "title": str(decision.offer_arm),
            "price": int(price_for_render),
            "currency": "₽",
            "what_user_gets": "",
        },
        "fallback_text": offer_text,
        "reply_markup": (offer_meta.get("reply_markup") if isinstance(offer_meta, dict) else None),
        "priority": "low",
        "best_effort": True,
        "critical": False,
        "track_event_type": "offer_shown",
        "track_payload": {
            "offer_id": str(decision.offer_arm),
            "arm": decision.offer_arm,
            "variant": str(offer_variant),
            "meta": offer_meta,
            "price_rub": int(price_for_render),
            "max_band": max_band,
            "day_index": int(decision.day_index),
            "day_key": str(decision.day_key),
        },
    }
    meta = {"offer_variant": str(offer_variant), "offer_meta": offer_meta, "price_for_render": int(price_for_render)}
    return step, meta
