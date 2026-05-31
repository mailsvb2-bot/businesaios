"""Offer keyboards (UI bundle).

Policy should not know button wiring.
OfferEngine may attach reply_markup into OfferRender.meta.
"""

from __future__ import annotations

from core.ux.inline_keyboards import inline_button, inline_keyboard


def offer_outcome_kb(offer_id: str, *, price_rub: int | None = None) -> dict:
    oid = str(offer_id or "").strip()
    # Backward-compatible extension:
    #   offer:accept:<offer_id>:<price_rub>
    # If price is missing, keep old 3-part format.
    suffix = f":{int(price_rub)}" if isinstance(price_rub, int) and price_rub > 0 else ""
    return inline_keyboard(
        [
            [inline_button("✅ Оплатить", f"offer:accept:{oid}{suffix}")],
            [inline_button("🙅 Не сейчас", f"offer:decline:{oid}{suffix}")],
        ]
    )
