from __future__ import annotations

from core.policies.telegram.context import TelegramCtx, policy_scope, scoped_active_plans, scoped_plan
from core.policies.telegram.handlers.admin.pricing_support import (
    ai_request_rows,
    back_markup,
    parse_ai_request_callback,
    parse_plan_callback_id,
    pending_requests_view,
    pricing_approve_request_payload,
    pricing_change_request_payload,
    pricing_edit_request_payload,
)
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def handle_pricing(ctx: TelegramCtx, *, pm) -> ProposedAction | None:
    if ctx.callback_data == "admin:ai:prices":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        from core.admin.ai_marketing import recommend_prices
        from core.economics.brain import EconomicBrain, EconomicReward, GrowthPolicy, LTVEstimator, PricingPolicy
        brain = EconomicBrain(ltv=LTVEstimator(), pricing=PricingPolicy(), growth=GrowthPolicy(), reward=EconomicReward())
        res = recommend_prices(brain=brain, metrics=(ctx.admin_metrics or {}), plans=scoped_active_plans(ctx))
        if not res.get("ok"):
            return pm(text=f"🤖 AI‑цены\n\nНе получилось: {res.get('reason')}", reply_markup=kb_staff_menu())
        lines = ["🤖 AI рекомендации цен\n"]
        for it in (res.get("items") or []):
            lines.append(f"• {it.get('title')}: {it.get('price')} ₽\n  {it.get('why')}")
        lines.append("\n⚠️ Это рекомендации. Изменение цен — через governed релиз/override.")
        return pm(text="\n".join(lines), reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:tariffs:show":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        plans = scoped_active_plans(ctx)
        if not plans:
            return pm(text="Тарифы не найдены.", reply_markup=kb_staff_menu())
        lines = ["💳 Тарифы (каталог)\n"]
        for p in plans:
            lines.append(f"• #{p['plan_id']} {p['title']} — {p['price']} ₽ / {p['days']}д ({p['scope']})")
        lines.append("\nРедактирование цен в prod — только через governed апдейт (без правки кода в рантайме).")
        return pm(text="\n".join(lines), reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:tariffs:history":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        txt = (
            "🧾 История тарифов\n\n"
            "В этом production-kernel история берётся из event-store (tariff_selected/payment_*).\n"
            "Для просмотра: открой events.sqlite и отфильтруй event_type.\n\n"
            "Следующий шаг (если нужно): сделать read-model 'tariff_changes' и показывать последние N событий."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:pricing:menu":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        plans = scoped_active_plans(ctx)
        rows = [[{"text": "📋 Pending requests", "callback_data": "admin:pricing:pending"}]]
        for p in plans:
            rows.append([
                {"text": f"✏️ #{p['plan_id']} {p['title']} — {p['price']}₽", "callback_data": f"admin:pricing:edit:{int(p['plan_id'])}"},
                {"text": "🤖 AI", "callback_data": f"admin:pricing:ai:{int(p['plan_id'])}"},
            ])
        rows.append([{"text": "⬅️ Назад", "callback_data": "admin:menu"}])
        txt = (
            "💸 Governed pricing\n\n"
            "1) Выбери тариф → введи новую цену (и опционально версию).\n"
            "2) Появится change-request.\n"
            "3) Любой admin из ADMIN_USER_IDS подтверждает → цена пишется в data/plans.json.\n\n"
            "Формат ввода: 2290 или 2290 v20.1"
        )
        return pm(text=txt, reply_markup={"inline_keyboard": rows})

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:edit:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        plan_id = parse_plan_callback_id(ctx.callback_data, prefix="admin:pricing:edit:")
        if plan_id is None:
            return pm(text="Некорректный plan_id.", reply_markup=kb_staff_menu())
        if scoped_plan(ctx, plan_id) is None:
            return pm(text="Тариф не найден в каталоге этого бизнеса.", reply_markup=kb_staff_menu())
        return propose("set_user_setting@v1", pricing_edit_request_payload(
            user_id=str(ctx.state.user_id), plan_id=plan_id, callback_query_id=ctx.callback_query_id,
            nonce=str(ctx.callback_query_id or getattr(ctx.state, "timestamp_ms", "") or ""),
        ))

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:ai:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        plan_id = parse_plan_callback_id(ctx.callback_data, prefix="admin:pricing:ai:")
        if plan_id is None:
            return pm(text="Некорректный plan_id.", reply_markup=kb_staff_menu())

        plan = scoped_plan(ctx, plan_id)
        if plan is None:
            return pm(text="Тариф не найден в каталоге этого бизнеса.", reply_markup=back_markup("admin:pricing:menu"))
        base_price = int(plan.get("price") or 0)
        try:
            suggested = int((ctx.pricing_suggestions or {}).get(str(plan_id)) or 0)
        except (TypeError, ValueError):
            suggested = 0
        method = "read_model" if suggested > 0 else "no_data"
        suggested = suggested if suggested > 0 else base_price
        return pm(
            text=(f"🤖 AI-подсказка цены для тарифа #{plan_id}\\n\\n"
                  f"Текущая: {base_price}₽\\nРекомендуемая: {suggested}₽\\n"
                  f"Источник: {method}. Это рекомендация, не изменение цены."),
            reply_markup=ai_request_rows(plan_id=plan_id, suggested_price=suggested),
        )

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:ai_request:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        parsed = parse_ai_request_callback(ctx.callback_data)
        if parsed is None:
            return pm(text="Некорректные параметры.", reply_markup=back_markup("admin:pricing:menu"))
        plan_id, new_price = parsed
        if scoped_plan(ctx, plan_id) is None or not policy_scope(ctx).has_business:
            return pm(text="Бизнес или тариф не выбран.", reply_markup=back_markup("admin:pricing:menu"))
        return propose("request_pricing_change@v1", pricing_change_request_payload(
            admin_id=str(ctx.state.user_id), plan_id=plan_id, new_price=new_price,
            nonce=str(ctx.callback_query_id or getattr(ctx.state, "timestamp_ms", "") or ""),
            reason="ai_suggested", callback_query_id=ctx.callback_query_id,
        ))

    if ctx.callback_data == "admin:pricing:pending":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        reqs = list((ctx.admin_metrics or {}).get("pricing_requests") or []) if isinstance(ctx.admin_metrics, dict) else []
        scope = policy_scope(ctx)
        reqs = [row for row in reqs if isinstance(row, dict)
                and row.get("product_id") == scope.product_id
                and row.get("business_id") == scope.business_id
                and scope.has_business]
        text, markup = pending_requests_view(reqs)
        return pm(text=text, reply_markup=markup)

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:approve:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        rid = str(ctx.callback_data.split(":", 3)[-1]).strip()
        if not rid:
            return pm(text="Некорректный request_id.", reply_markup=kb_staff_menu())
        return propose("set_user_setting@v1", pricing_approve_request_payload(user_id=str(ctx.state.user_id), request_id=rid, callback_query_id=ctx.callback_query_id))

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:reject:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        rid = str(ctx.callback_data.split(":", 3)[-1]).strip()
        if not rid or not policy_scope(ctx).has_business:
            return pm(text="Запрос или бизнес не выбран.", reply_markup=kb_staff_menu())
        return propose(
            "reject_pricing_change@v1",
            {
                "admin_id": str(ctx.state.user_id),
                "request_id": rid,
                "notify_text": f"❌ Rejected request {rid[:8]}.",
                "notify_reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "admin:pricing:pending"}]]},
                "callback_query_id": ctx.callback_query_id,
            },
        )

    return None
