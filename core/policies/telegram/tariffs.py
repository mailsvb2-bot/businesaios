from __future__ import annotations

from typing import Any

from core.policies.telegram.helpers import ProposedAction, choose_marketing_variant, propose, propose_message
from core.policies.telegram.tariffs_text import build_plan_confirmation_text

# Public compatibility export used by other Telegram policy modules.
from core.policies.telegram.tariffs_text import scope_hint as scope_hint
from core.ux.telegram_keyboards import kb_back_main, kb_pay_selected, kb_tariffs


def propose_show_tariffs(
    *,
    user_id: str,
    legacy_prices: dict[str, int],
    pricing_suggestions: dict[str, int] | None = None,
    marketing_variants: dict[str, dict[str, str]] | None = None,
    marketing_seed: str = "1",
    marketing_bandit: dict[str, dict[str, dict[str, float]]] | None = None,
    plans: list[dict[str, Any]] | None = None,
) -> ProposedAction:
    step = "tariffs_viewed"
    v = choose_marketing_variant(
        user_id=str(user_id),
        step_key=step,
        seed=str(marketing_seed or "1"),
        bandit=(marketing_bandit or {}).get(step) if isinstance(marketing_bandit, dict) else None,
    )
    variants = (marketing_variants or {}).get(step) or {}
    msg = str(variants.get(v) or variants.get("a") or variants.get("b") or "💳 Тарифы\n\nВыбери тариф:")
    try:
        plans = list(plans or [])
        # Checkout displays only the authoritative scoped catalog price.
        # AI pricing suggestions are advisory and cannot replace a sale price.
        return propose_message(
            user_id=user_id,
            text=msg,
            reply_markup=kb_tariffs(plans),
            track_event_type="tariffs_viewed",
            track_payload={"marketing_variant": v},
        )
    except Exception:
        # Fail closed; never resurrect legacy therapy tariffs on catalog failure.
        return propose_message(
            user_id=user_id,
            text="Тарифы сейчас недоступны.",
            reply_markup=kb_tariffs([]),
            track_event_type="tariffs_viewed",
            track_payload={"marketing_variant": v, "catalog_status": "unavailable"},
        )


def parse_sub_buy(cb: str) -> tuple[int, int | None] | None:
    # Format: sub:buy:<plan_id>:<expected_price?>
    parts = (cb or "").split(":")
    if len(parts) < 3 or parts[0] != "sub" or parts[1] != "buy":
        return None
    try:
        plan_id = int(parts[2])
    except Exception:
        return None
    expected = None
    if len(parts) >= 4:
        try:
            expected = int(parts[3])
        except Exception:
            expected = None
    return plan_id, expected


def propose_select_tariff(*, user_id: str, plan_id: int, expected_price: int | None,
                          tenant_id: str | None = None, product_id: str | None = None) -> ProposedAction:
    """Select a tariff/plan (effect proposal).

    IMPORTANT:
    - select_tariff@v1 schema requires tariff/days/period/amount.
    - We resolve these fields from the immutable plan catalog here (pure).
    """
    try:
        from core.plans import get_plan_by_id

        plan = get_plan_by_id(int(plan_id), tenant_id=tenant_id, product_id=product_id)
    except Exception:
        plan = None

    if not isinstance(plan, dict):
        return propose_message(user_id=str(user_id), text="Тариф недоступен.", reply_markup=kb_back_main())

    title = str(plan.get("title") or "Тариф").strip()
    days = int(plan.get("days") or 0)
    tariff = str(plan.get("plan_code") or plan.get("code") or f"plan:{int(plan_id)}").strip()
    base_price = int(plan.get("price") or 0)
    if expected_price is not None and int(expected_price) != base_price:
        return propose_message(user_id=str(user_id), text="Цена изменилась. Выберите тариф заново.", reply_markup=kb_back_main())
    amount = base_price

    txt = build_plan_confirmation_text({**dict(plan), "price": int(amount)})
    return propose(
        "select_tariff@v1",
        {
            "user_id": str(user_id),
            "tariff": str(tariff),
            "days": int(days),
            "period": str(plan.get("scope") or "days"),
            "amount": int(amount),
            "plan_id": int(plan_id),
            "title": str(title),
            "expected_price": int(expected_price) if expected_price is not None else None,
            "notify_text": txt,
            "notify_reply_markup": kb_pay_selected(),
        },
    )


def checkout_order_id(*, tenant_id: str, business_id: str, product_id: str,
                      user_id: str, plan_id: int, amount: int, selected_ts: object) -> str:
    import hashlib

    identity = "|".join(str(value) for value in (
        tenant_id, business_id, product_id, user_id, plan_id, amount, selected_ts,
    ))
    return "tg-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def propose_pay_selected(*, user_id: str, full_access: bool,
                         selected: dict[str, Any] | None,
                         tenant_id: str | None = None, product_id: str | None = None,
                         business_id: str | None = None, checkout_enabled: bool = False,
                         **_legacy: Any) -> ProposedAction:
    """One tenant/business/product-bound Telegram PSP checkout path."""
    if full_access:
        return propose_message(user_id=user_id, text="Полный доступ уже активен ✅",
                               reply_markup=kb_back_main())
    tenant, product, business = (str(value or "").strip() for value in
                                 (tenant_id, product_id, business_id))
    if not tenant or not product or not business:
        return propose_message(user_id=user_id, text="Оплата недоступна: бизнес не привязан.",
                               reply_markup=kb_back_main())
    selected = dict(selected or {})
    if not selected.get("plan_id"):
        return propose_message(user_id=user_id, text="Сначала выберите доступный тариф.",
                               reply_markup=kb_back_main())
    if selected.get("tenant_id") != tenant or selected.get("product_id") != product:
        return propose_message(user_id=user_id, text="Тариф другого продукта или организации недоступен.",
                               reply_markup=kb_back_main())
    try:
        from core.plans import plan_by_id

        plan = plan_by_id(int(selected["plan_id"]), tenant_id=tenant, product_id=product)
        current = int((plan or {}).get("price") or 0)
        expected = int(selected.get("expected_price", selected.get("amount")))
    except (ValueError, TypeError):
        plan, current, expected = None, 0, 0
    if not plan or current <= 0:
        return propose_message(user_id=user_id, text="Тариф сейчас недоступен.",
                               reply_markup=kb_back_main())
    if expected != current:
        return propose_message(user_id=user_id, text="Цена изменилась. Выберите тариф заново.",
                               reply_markup=kb_back_main())
    if not checkout_enabled:
        return propose_message(
            user_id=user_id,
            text="Оплата в Telegram выключена оператором. Оформите заказ в веб-кабинете.",
            reply_markup=kb_back_main(),
        )
    return propose("create_payment_and_send_link@v1", {
        "user_id": str(user_id), "tenant_id": tenant, "business_id": business,
        "product_id": product,
        "order_id": checkout_order_id(
            tenant_id=tenant, business_id=business, product_id=product,
            user_id=str(user_id), plan_id=int(selected["plan_id"]),
            amount=current, selected_ts=selected.get("ts"),
        ),
        "amount": current * 100, "expected_amount": current * 100,
        "currency": "RUB",
        "metadata": {"plan_id": int(selected["plan_id"]),
                     "plan_code": str(plan.get("plan_code") or ""),
                     "description": str(plan.get("title") or "Тариф")[:128]},
    })
