"""Offer acceptance and rejection through one canonical, non-payment message.

The original composite execute_plan route was not executable under the
single-envelope executor lock. A Telegram callback never establishes a trusted
catalog price, product order or payment identity.
"""
from __future__ import annotations

from core.offers.offer_callbacks import outcome_event_type, parse_offer_callback
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose_message
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.ux.telegram_keyboards import kb_main
from core.ux.unified_messenger_menu import BUSINESS_ONBOARDING_URL


def handle_offer_outcome(
    ctx: TelegramCtx, *, user_id: str, default_price_rub: int,
) -> ProposedAction | None:
    del default_price_rub  # Prices belong to the verified server catalog.
    cb = str(ctx.callback_data or "")
    if not cb.startswith("offer:"):
        return None
    offer = parse_offer_callback(cb)
    if offer is None:
        return None

    tenant_id = normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None))
    product = getattr(ctx.state, "product", None) or {}
    product = product if isinstance(product, dict) else {}
    tracked = {
        "offer_id": str(offer.offer_id),
        "kind": str(offer.kind),
        "tenant_id": tenant_id,
        "product_id": str(product.get("product_id") or product.get("id") or "organization_platform"),
        "domain": str(product.get("domain") or "organization_platform"),
        "payment_confirmed": False,
    }
    if offer.kind == "accept":
        text = (
            "✅ Интерес к предложению отмечен.\n\n"
            "Для создания заказа и счёта откройте рабочее пространство. "
            "Сумму и доступность предложения подтверждает только серверный каталог. "
            "Нажатие здесь не создаёт платёж и не подтверждает оплату."
        )
        keyboard = {"inline_keyboard": [
            [{"text": "🌐 Перейти к оформлению", "url": BUSINESS_ONBOARDING_URL}],
            [{"text": "⬅️ Главное меню", "callback_data": "menu:main"}],
        ]}
    else:
        text = "Понял. Без давления. Вернёмся позже."
        keyboard = kb_main(is_admin=ctx.is_admin)

    return propose_message(
        user_id=str(user_id),
        text=text,
        reply_markup=keyboard,
        callback_query_id=ctx.callback_query_id,
        track_event_type=outcome_event_type(offer.kind),
        track_payload=tracked,
    )
