from __future__ import annotations

import time
from typing import Any, Dict, Tuple

from core.offers.engine import OfferEngine
from core.observability.throttled_logger import exception_throttled


def cap_price_by_band(*, product: dict, price_rub: int, max_band: str | None) -> int:
    if not max_band:
        return int(price_rub)
    try:
        params = ((product.get("pricing_model") or {}).get("params") or {}) if isinstance(product, dict) else {}
        ladder = params.get("ladder") if isinstance(params, dict) else None
        if not isinstance(ladder, dict):
            return int(price_rub)
        cap = ladder.get(max_band)
        return min(int(price_rub), int(cap)) if cap is not None else int(price_rub)
    except Exception:
        return int(price_rub)


def should_allow_offer(*, offer_engine: OfferEngine, cooldown_store: Any, state: Any, tenant_id: str, user_id: str, offer_id: str) -> bool:
    try:
        product = getattr(state, "product", None) or {}
        entitlements = {}
        user = getattr(state, "user", None) or {}
        if isinstance(user, dict):
            entitlements = user.get("entitlements") or {}
        session = getattr(state, "session", None) or {}
        payment_status = session.get("payment_status") if isinstance(session, dict) else None
        ok, _meta = offer_engine.should_show_offer(
            now_ms=int(time.time() * 1000),
            product=product if isinstance(product, dict) else {},
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            entitlements=entitlements if isinstance(entitlements, dict) else {},
            payment_status=str(payment_status) if payment_status is not None else None,
            offer_id=str(offer_id),
            cooldown_store=cooldown_store,
        )
        return bool(ok)
    except Exception:
        return True


def render_offer_payload(*, offer_engine: OfferEngine, state: Any, tenant_id: str, user_id: str, offer_id: str, price_rub: int, day_key: str, day_index: int, max_band: str | None, default_logger: Any) -> Tuple[str, str, Dict[str, Any], int]:
    try:
        product = getattr(state, "product", None) or {}
    except Exception:
        product = {}
    price_for_render = int(price_rub)
    try:
        if isinstance(product, dict):
            price_for_render = cap_price_by_band(product=product, price_rub=int(price_rub), max_band=max_band)
    except Exception:
        price_for_render = int(price_rub)
    try:
        rendered = offer_engine.render_offer(
            product=product if isinstance(product, dict) else {},
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            offer_id=str(offer_id),
            price_rub=int(price_for_render),
            step_key=f"offer:{offer_id}",
            seed=str(getattr(state, "marketing_seed", "1") if hasattr(state, "marketing_seed") else "1"),
            bandit=None,
            context={"tenant_id": str(tenant_id), "day_key": str(day_key), "day_index": int(day_index)},
        )
        return rendered.text, rendered.variant, dict(rendered.meta or {}), int(price_for_render)
    except Exception:
        exception_throttled(default_logger, key=f'retention.offer_render|{user_id}', msg='retention: offer render fallback used')
        return f"💡 Предложение: {offer_id} за {int(price_for_render)} ₽", "a", {}, int(price_for_render)
