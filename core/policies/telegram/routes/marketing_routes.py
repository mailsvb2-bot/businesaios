from __future__ import annotations

from typing import Optional

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.policies.telegram.tariffs import (
    build_plan_confirmation_text,
    parse_sub_buy,
    propose_pay_selected,
    propose_show_tariffs,
    scope_hint,
)
from core.ux.callbacks import CB_PAY_SELECTED, CB_SHARE_MENU, CB_SUB_MENU
from core.ux.telegram_keyboards import kb_back_main, kb_main, kb_pay_selected


def handle_marketing_routes(
    ctx: TelegramCtx,
    *,
    user_id: str,
    default_price_rub: int,
    legacy_prices: dict,
    bot_username: str,
    pm,
) -> Optional[ProposedAction]:
    if ctx.callback_data == CB_SHARE_MENU:
        bot = (str(bot_username or "")).strip().lstrip("@")
        if not bot:
            msg = (
                "📣 Посоветовать\n\n"
                "Пока не могу собрать ссылку: неизвестен username бота.\n"
                "FIX: добавь BOT_USERNAME в env/.env (без @) или запусти RUN_MODE=telegram — "
                "на старте мы берём username через getMe и заполняем BOT_USERNAME автоматически."
            )
            return pm(text=msg, reply_markup=kb_back_main())
        return pm(
            text=(
                "📣 Посоветовать\n\n"
                "Скопируй и отправь другу:\n"
                f"https://t.me/{bot}\n\n"
                "(Если хочешь реферальную ссылку — добавим в следующем релизе.)"
            ),
            reply_markup=kb_back_main(),
        )
    if ctx.callback_data == CB_SUB_MENU:
        return propose_show_tariffs(
            user_id=user_id,
            legacy_prices=legacy_prices,
            marketing_variants=ctx.marketing_variants,
            marketing_seed=ctx.marketing_seed,
            marketing_bandit=ctx.marketing_bandit,
            pricing_suggestions=getattr(ctx, "pricing_suggestions", None),
        )
    sub_buy = parse_sub_buy(ctx.callback_data)
    if sub_buy is not None:
        plan_id, expected = sub_buy
        try:
            from core.plans import plan_by_id

            plan = plan_by_id(int(plan_id))
        except Exception:
            plan = None
        if not plan:
            return pm(text="❌ Тариф не найден.", reply_markup=kb_back_main())
        current_price = int(plan.get("price") or 0)
        if current_price <= 0:
            return pm(text="⚠️ Цена для выбранного тарифа не задана.", reply_markup=kb_back_main())
        if expected is not None and int(expected) != int(current_price):
            return pm(text="Цена только что обновилась.\nПожалуйста, выберите тариф ещё раз:", reply_markup=kb_back_main())
        return propose(
            "select_tariff@v1",
            {
                "user_id": user_id,
                "tariff": str(plan.get("plan_code") or plan.get("code") or ""),
                "days": int(plan.get("days") or 0),
                "period": str(plan.get("scope") or ""),
                "amount": int(current_price),
                "plan_id": int(plan_id),
                "title": str(plan.get("title") or ""),
                "expected_price": int(current_price),
                "notify_text": build_plan_confirmation_text(plan),
                "notify_reply_markup": kb_pay_selected(),
                "notify": True,
            },
        )
    if str(ctx.callback_data or "").startswith("sub:") and str(ctx.callback_data).count(":") == 2:
        try:
            _, period, days_s = str(ctx.callback_data).split(":", 2)
            days = int(days_s)
        except Exception:
            return pm(text="Некорректный тариф.", reply_markup=kb_back_main())
        title_map = {
            ("morning", 5): "Утро — 5 дней",
            ("morning", 20): "Утро — 20 дней",
            ("evening", 5): "Вечер — 5 дней",
            ("evening", 20): "Вечер — 20 дней",
            ("both", 5): "Утро+Вечер — 5 дней",
            ("both", 20): "Утро+Вечер — 20 дней",
        }
        title = title_map.get((period, days)) or str(ctx.callback_data)
        amount = int(legacy_prices.get(str(title), int(default_price_rub)))
        notify = build_plan_confirmation_text(
            {
                "title": str(title),
                "price": int(amount),
                "days": int(days),
                "scope": str(period),
                "terms_short": "Оплата разовая. Доступ выдаётся автоматически после успешной оплаты.",
            }
        )
        return propose(
            "select_tariff@v1",
            {
                "user_id": user_id,
                "tariff": str(title),
                "days": int(days),
                "period": str(period),
                "amount": int(amount),
                "notify_text": notify,
                "notify_reply_markup": kb_pay_selected(),
                "notify": True,
            },
        )
    if ctx.cmd == "/pay":
        if not ctx.selected_tariff:
            return propose_show_tariffs(
                user_id=user_id,
                legacy_prices=legacy_prices,
                marketing_variants=ctx.marketing_variants,
                marketing_seed=ctx.marketing_seed,
                marketing_bandit=ctx.marketing_bandit,
            )
        return propose_pay_selected(
            user_id=user_id,
            full_access=ctx.full_access,
            selected=ctx.selected_tariff,
            default_price_rub=int(default_price_rub),
            legacy_prices=legacy_prices,
        )
    if str(ctx.callback_data or "").startswith(CB_PAY_SELECTED):
        return propose_pay_selected(
            user_id=user_id,
            full_access=ctx.full_access,
            selected=ctx.selected_tariff,
            default_price_rub=int(default_price_rub),
            legacy_prices=legacy_prices,
        )
    if ctx.pay_status in {"succeeded", "paid", "success"} and not ctx.full_access:
        selected = dict(ctx.selected_tariff or {})
        scope = str(selected.get("period") or "")
        title = str(selected.get("title") or "")
        days = int(selected.get("days") or 0)
        note_lines = ["Оплата получена ✅"]
        if title:
            note_lines.append(f"Тариф: {title}")
        if days > 0:
            note_lines.append(f"Длительность: {days} дней")
        note_lines.append(f"Ритм: {scope_hint(scope)}")
        note_lines.append("")
        note_lines.append("Если хочешь — укажи город: /city Amsterdam")
        return propose(
            "grant_access@v1",
            {
                "user_id": user_id,
                "full_access": True,
                "notify_text": "\n".join(note_lines),
                "notify_reply_markup": kb_main(is_admin=ctx.is_admin),
            },
        )
    return None
