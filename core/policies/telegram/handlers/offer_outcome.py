from __future__ import annotations

"""Offer outcome callback handler.

Why separate module:
- Router stays readable (no "god router")
- Single canonical place for multi-step offer accept/decline flow
- Prevents accidental divergence ("two lines" for offer callbacks)
"""


from core.offers.offer_callbacks import outcome_event_type, parse_offer_callback
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.ux.telegram_keyboards import kb_main


def handle_offer_outcome(
    ctx: TelegramCtx,
    *,
    user_id: str,
    default_price_rub: int,
) -> ProposedAction | None:
    # Only handle our canonical prefix.
    if not (isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("offer:")):
        return None

    ocb = parse_offer_callback(ctx.callback_data)
    if ocb is None:
        return None

    tenant_id = normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None))
    product = getattr(ctx.state, "product", None) or {}
    product_id = str(product.get("product_id") or product.get("id") or "organization_platform")
    domain = str(product.get("domain") or "organization_platform")

    steps = []

    # Always stop Telegram button loader if possible.
    if ctx.callback_query_id:
        steps.append({"action": "answer_callback@v1", "callback_query_id": str(ctx.callback_query_id), "text": "Ок"})

    # Tracking (pure).
    steps.append(
        {
            "action": "track_event@v1",
            "user_id": user_id,
            "event_type": outcome_event_type(ocb.kind),
            "payload": {
                "offer_id": str(ocb.offer_id),
                "kind": str(ocb.kind),
                "tenant_id": tenant_id,
                "product_id": product_id,
                "domain": domain,
            },
        }
    )

    if str(ocb.kind) == "accept":
        # Best-effort price resolution: callback.price_rub -> selected_tariff.price_rub -> default.
        amount = None
        try:
            if isinstance(ocb.meta, dict) and ocb.meta.get("price_rub"):
                amount = int(ocb.meta.get("price_rub") or 0) or None
        except Exception:
            amount = None
        try:
            if isinstance(ctx.selected_tariff, dict):
                amount = int(ctx.selected_tariff.get("price_rub") or ctx.selected_tariff.get("price") or 0) or None
        except Exception:
            amount = None
        if amount is None:
            amount = int(default_price_rub)

        steps.append(
            {
                "action": "create_payment_and_send_link@v1",
                "user_id": user_id,
                "amount": int(amount),
                "currency": "RUB",
                "metadata": {
                    "offer_id": str(ocb.offer_id),
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "domain": domain,
                    "grant_key": f"{tenant_id}:{str(ocb.offer_id)}",
                },
            }
        )
        return {"action": "execute_plan@v1", "user_id": user_id, "steps": steps}

    # decline: send a gentle message (no payment).
    steps.append(
        {
            "action": "send_message@v1",
            "user_id": user_id,
            "text": "Понял. Без давления. Вернёмся позже.",
            "reply_markup": kb_main(is_admin=ctx.is_admin),
            "priority": "low",
            "best_effort": True,
            "critical": False,
        }
    )
    return {"action": "execute_plan@v1", "user_id": user_id, "steps": steps}
