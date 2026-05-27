from __future__ import annotations

from typing import Any

from core.observability.silent import swallow
from core.offers.engine import OfferEngine
from core.policies.sales.sales_keyboards import sales_main_kb
from core.policies.telegram.helpers import ProposedAction, propose, propose_message

_OFFER_ENGINE: OfferEngine | None = None


def _offer_engine() -> OfferEngine:
    global _OFFER_ENGINE
    if _OFFER_ENGINE is None:
        _OFFER_ENGINE = OfferEngine.default()
    return _OFFER_ENGINE


def safe_offer_payload(rend: Any, *, currency: str = "₽") -> dict[str, Any]:
    meta = {}
    try:
        meta = dict(getattr(rend, "meta", {}) or {})
    except Exception:
        meta = {}
    offer_id = str(getattr(rend, "offer_id", "") or "")
    title = str(meta.get("title") or meta.get("name") or meta.get("label") or offer_id or "Предложение")
    what = str(meta.get("what_user_gets") or meta.get("deliverable") or meta.get("description") or "").strip()
    price_rub = int(getattr(rend, "price_rub", 0) or 0)
    return {
        "id": offer_id,
        "title": title,
        "price": price_rub if price_rub > 0 else "",
        "currency": currency,
        "what_user_gets": what,
    }


def safe_reply_markup(rend: Any) -> dict[str, Any] | None:
    try:
        markup = (getattr(rend, "meta", {}) or {}).get("reply_markup")
        if isinstance(markup, dict) and markup:
            return markup
    except Exception:
        swallow(__name__, "core/policies/product_domains/sales_domain_support.py")
    return None


def _fallback_offer_action(*, user_id: str, callback_query_id: str | None, step_key: str, track_event_type: str, fallback_text: str, reason: str) -> ProposedAction:
    return propose_message(
        user_id=user_id,
        text=fallback_text,
        reply_markup=sales_main_kb(),
        callback_query_id=callback_query_id,
        track_event_type=track_event_type,
        track_payload={
            "offer_id": "offer_30",
            "variant": "fallback",
            "price_rub": 600,
            "domain": "sales",
            "step_key": step_key,
            "reason": reason,
        },
    )


def build_offer_action(*, state: Any, user_id: str, tenant_id: str, locale: str, last_user_text: str, callback_query_id: str | None, step_key: str, context: dict[str, Any], action_name: str, track_event_type: str, fallback_text: str) -> ProposedAction:
    prod = {}
    try:
        prod = dict(getattr(state, "product", {}) or {})
    except Exception:
        prod = {}
    seed = str(getattr(state, "marketing_seed", "1") if hasattr(state, "marketing_seed") else "1")
    try:
        rend = _offer_engine().render_offer(
            product=prod,
            tenant_id=tenant_id,
            user_id=user_id,
            offer_id="offer_30",
            price_rub=600,
            step_key=step_key,
            seed=seed,
            bandit=None,
            context=context,
        )
    except Exception:
        swallow(__name__, "core/policies/product_domains/sales_domain_support.py:render_offer")
        return _fallback_offer_action(
            user_id=user_id,
            callback_query_id=callback_query_id,
            step_key=step_key,
            track_event_type=track_event_type,
            fallback_text=fallback_text,
            reason="render_offer_failed",
        )

    offer = safe_offer_payload(rend)
    reply_markup = safe_reply_markup(rend) or sales_main_kb()
    variant = str(getattr(rend, "variant", "") or "")
    return propose(
        action_name,
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "locale": locale,
            "channel": "telegram",
            "offer": offer,
            "features": dict((getattr(state, "user", {}) or {}).get("behavioral_state") or {}),
            "last_user_text": last_user_text,
            "reply_markup": reply_markup,
            "callback_query_id": callback_query_id,
            "track_event_type": track_event_type,
            "track_payload": {
                "offer_id": offer.get("id"),
                "price_rub": int(offer.get("price") or 0),
                "domain": "sales",
                "step_key": step_key,
                "variant": variant,
                "offer_variant": variant,
                "marketing_variant": variant,
            },
        },
    )
