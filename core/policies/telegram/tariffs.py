from __future__ import annotations

from typing import Any, Optional

from core.observability.silent import swallow
from core.policies.telegram.helpers import ProposedAction, choose_marketing_variant, propose, propose_message
from core.policies.telegram.tariffs_text import build_plan_confirmation_text, scope_hint
from core.ux.telegram_keyboards import kb_back_main, kb_pay_selected, kb_sub, kb_tariffs


def propose_show_tariffs(
    *,
    user_id: str,
    legacy_prices: dict[str, int],
    pricing_suggestions: dict[str, int] | None = None,
    marketing_variants: dict[str, dict[str, str]] | None = None,
    marketing_seed: str = "1",
    marketing_bandit: dict[str, dict[str, dict[str, float]]] | None = None,
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
        from core.plans import active_plans

        plans = list(active_plans())
        # Optional autopricing: override displayed price for plan_id if suggested.
        try:
            sug = dict(pricing_suggestions or {})
            if sug:
                out_plans = []
                for p in plans:
                    try:
                        pid = str(int(p.get('plan_id') or 0))
                        if pid in sug and int(sug[pid]) > 0:
                            p2 = dict(p)
                            p2['price'] = int(sug[pid])
                            out_plans.append(p2)
                        else:
                            out_plans.append(p)
                    except Exception:
                        out_plans.append(p)
                plans = out_plans
        except Exception:
            swallow(__name__, 'core/policies/telegram/tariffs.py')
        return propose_message(
            user_id=user_id,
            text=msg,
            reply_markup=kb_tariffs(plans),
            track_event_type="tariffs_viewed",
            track_payload={"marketing_variant": v},
        )
    except Exception:
        return propose_message(
            user_id=user_id,
            text=msg,
            reply_markup=kb_sub(legacy_prices),
            track_event_type="tariffs_viewed",
            track_payload={"marketing_variant": v},
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


def propose_select_tariff(*, user_id: str, plan_id: int, expected_price: int | None) -> ProposedAction:
    """Select a tariff/plan (effect proposal).

    IMPORTANT:
    - select_tariff@v1 schema requires tariff/days/period/amount.
    - We resolve these fields from the immutable plan catalog here (pure).
    """
    try:
        from core.plans import get_plan_by_id

        plan = get_plan_by_id(int(plan_id))
    except Exception:
        plan = None

    if not isinstance(plan, dict):
        # Safe fallback: keep the effect minimal; executor may reject in strict mode.
        return propose(
            "select_tariff@v1",
            {
                "user_id": str(user_id),
                "tariff": f"plan:{int(plan_id)}",
                "days": 0,
                "period": "days",
                "amount": int(expected_price) if expected_price is not None else 0,
                "plan_id": int(plan_id),
                "expected_price": int(expected_price) if expected_price is not None else None,
                "notify_text": "⚠️ Тариф не найден. Попробуйте выбрать другой.",
                "notify_reply_markup": kb_back_main(),
            },
        )

    title = str(plan.get("title") or "Тариф").strip()
    days = int(plan.get("days") or 0)
    tariff = str(plan.get("plan_code") or plan.get("code") or f"plan:{int(plan_id)}").strip()
    base_price = int(plan.get("price") or 0)
    amount = int(expected_price) if expected_price is not None else int(base_price)

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


def propose_pay_selected(*, user_id: str, full_access: bool, selected: dict[str, Any] | None, default_price_rub: int, legacy_prices: dict[str, int]) -> ProposedAction:
    if full_access:
        return propose_message(user_id=user_id, text="Полный доступ уже активен ✅", reply_markup=kb_back_main())

    selected = dict(selected or {})
    amount_rub: int | None = None
    meta_note: dict[str, Any] = {"selected": {}}

    plan_id = selected.get("plan_id")
    expected_price = selected.get("expected_price")
    if plan_id is not None:
        try:
            from core.plans import plan_by_id

            plan = plan_by_id(int(plan_id))
        except Exception:
            plan = None
        if not plan:
            return propose_message(user_id=user_id, text="Сначала выберите тариф.", reply_markup=kb_back_main())
        current_price = int(plan.get("price") or 0)
        if current_price <= 0:
            return propose_message(user_id=user_id, text="Тариф недоступен. Выберите другой.", reply_markup=kb_back_main())
        if expected_price is not None and int(current_price) != int(expected_price):
            return propose_message(
                user_id=user_id,
                text="Цена только что обновилась.\nПожалуйста, выберите тариф ещё раз:",
                reply_markup=kb_back_main(),
            )
        amount_rub = int(current_price)
        meta_note["selected"] = {
            "plan_id": int(plan_id),
            "tariff": plan.get("plan_code"),
            "title": plan.get("title"),
            "period": plan.get("scope"),
            "days": plan.get("days"),
            "price_rub": int(current_price),
        }
    else:
        amount_rub = int(default_price_rub)
        meta_note["selected"] = {"default": True, "price_rub": int(amount_rub)}

    return propose(
        "create_payment_and_send_link@v1",
        {
            "user_id": str(user_id),
            "amount": int(amount_rub) * 100,
            "currency": "RUB",
            "metadata": meta_note,
        },
    )
