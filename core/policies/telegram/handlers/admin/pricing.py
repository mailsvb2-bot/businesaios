from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu
from core.policies.telegram.handlers.admin.pricing_support import (
    ai_request_rows,
    back_markup,
    parse_ai_request_callback,
    parse_plan_callback_id,
    pending_requests_view,
    pricing_edit_request_payload,
    pricing_session_payload,
    pricing_approve_request_payload,
)


def handle_pricing(ctx: TelegramCtx, *, pm) -> ProposedAction | None:
    if ctx.callback_data == "admin:ai:prices":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        from core.economics.brain import EconomicBrain, LTVEstimator, PricingPolicy, GrowthPolicy, EconomicReward
        from core.admin.ai_marketing import recommend_prices
        from core.plans import active_plans

        brain = EconomicBrain(ltv=LTVEstimator(), pricing=PricingPolicy(), growth=GrowthPolicy(), reward=EconomicReward())
        res = recommend_prices(brain=brain, metrics=(ctx.admin_metrics or {}), plans=active_plans())
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
        from core.plans import active_plans

        plans = active_plans()
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
        from core.plans import active_plans

        plans = active_plans()
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
        plan_id = parse_plan_callback_id(ctx.callback_data, prefix="admin:pricing:ai:")
        if plan_id is None:
            return pm(text="Некорректный plan_id.", reply_markup=kb_staff_menu())
        return propose("set_user_setting@v1", pricing_edit_request_payload(user_id=str(ctx.state.user_id), plan_id=plan_id, callback_query_id=ctx.callback_query_id))

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:ai:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        plan_id = parse_plan_callback_id(ctx.callback_data, prefix="admin:pricing:ai:")
        if plan_id is None:
            return pm(text="Некорректный plan_id.", reply_markup=kb_staff_menu())

        from core.plans import active_plans
        from core.admin.ai_pricing import suggest_price_for_plan

        plans = active_plans()
        plan_by_id = {int(x.get("plan_id") or 0): x for x in plans}
        plan = plan_by_id.get(int(plan_id))
        if not plan:
            return pm(text="Тариф не найден.", reply_markup=back_markup("admin:pricing:menu"))

        base_price = int(plan.get("price") or 0)
        tid = str(getattr(ctx.state, "tenant_id", "") or "").strip()
        if not tid:
            return pm(text="❌ tenant_id не задан. Это strict режим: протащи tenant_id из BootContext/ProductContext.", reply_markup=back_markup("admin:pricing:menu"))
        sug = suggest_price_for_plan(ctx.event_store, tenant_id=tid, plan_id=int(plan_id), base_price=int(base_price))

        txt = (
            f"🤖 AI-подсказка цены для тарифа #{plan_id}\n\n"
            f"Текущая: {int(base_price)}₽\n"
            f"Рекомендуемая: {int(sug.suggested_price)}₽\n\n"
            f"Данные: выборов={int(sug.samples)}, оплат={int(sug.successes)} (окно {int(sug.window_hours)}ч)\n"
            f"Метод: {sug.method}\n"
            f"{sug.note}"
        )
        return pm(text=txt, reply_markup=ai_request_rows(plan_id=int(plan_id), suggested_price=int(sug.suggested_price)))

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:ai_request:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        parsed = parse_ai_request_callback(ctx.callback_data)
        if parsed is None:
            return pm(text="Некорректные параметры.", reply_markup=back_markup("admin:pricing:menu"))
        plan_id, new_price = parsed

        return propose(
            "request_pricing_change@v1",
            {
                "requested_by": str(ctx.state.user_id),
                "plan_id": int(plan_id),
                "new_price": int(new_price),
                "suggested_pricing_version": "",
                "note": "ai_suggested",
                "callback_query_id": ctx.callback_query_id,
                "notify_text": f"✅ Создан change-request: тариф #{plan_id} → {new_price}₽\n\nТеперь открой Pending requests и подтверди.",
                "notify_reply_markup": {"inline_keyboard": [[{"text": "📋 Pending requests", "callback_data": "admin:pricing:pending"}], [{"text": "⬅️ Назад", "callback_data": "admin:pricing:menu"}]]},
            },
        )

    if ctx.callback_data == "admin:pricing:pending":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        reqs = list((ctx.admin_metrics or {}).get("pricing_requests") or []) if isinstance(ctx.admin_metrics, dict) else []
        text, markup = pending_requests_view(reqs)
        return pm(text=text, reply_markup=markup)

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:approve:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        rid = str(ctx.callback_data.split(":", 3)[-1]).strip()
        return propose("set_user_setting@v1", pricing_approve_request_payload(user_id=str(ctx.state.user_id), request_id=rid, callback_query_id=ctx.callback_query_id))

    if isinstance(ctx.callback_data, str) and ctx.callback_data.startswith("admin:pricing:reject:"):
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        rid = str(ctx.callback_data.split(":", 3)[-1]).strip()
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
