from __future__ import annotations

from core.policies.telegram.context import TelegramCtx, policy_scope, scoped_active_plans
from core.policies.telegram.handlers.admin_handlers import handle_admin
from core.policies.telegram.handlers.admin_pricing import handle_admin_pricing_session
from core.policies.telegram.handlers.ads_apply import handle_ads_apply
from core.policies.telegram.handlers.ads_apply_flow import handle_ads_apply_flow
from core.policies.telegram.handlers.ai_ceo import handle_ai_ceo
from core.policies.telegram.handlers.autopilot import handle_autopilot
from core.policies.telegram.handlers.gift import handle_gift
from core.policies.telegram.handlers.growth_strategy import handle_growth_strategy
from core.policies.telegram.handlers.offer_outcome import handle_offer_outcome
from core.policies.telegram.helpers import (
    ProposedAction,
    build_legacy_prices,
    choose_marketing_variant,
    propose_message,
)
from core.policies.telegram.routes.business_flow_routes import handle_sales_buttons
from core.policies.telegram.routes.command_routes import handle_command_routes, handle_free_text
from core.policies.telegram.routes.customer_bot_routes import handle_customer_bot, is_customer_session
from core.policies.telegram.routes.marketing_routes import handle_marketing_routes
from core.policies.telegram.routes.settings_routes import handle_settings_routes
from core.users.roles import effective_role, has_permission, required_permission
from core.ux.callbacks import CB_MENU_MAIN
from core.ux.telegram_keyboards import kb_back_main, kb_main
from core.ux.unified_messenger_menu import menu_text


def handle(ctx: TelegramCtx, *, default_price_rub: int, bot_username: str = "", gift_ttl_sec: int = 7 * 24 * 3600) -> ProposedAction:
    user_id = ctx.state.user_id or "anonymous"
    if is_customer_session(getattr(ctx.state, "session", None)):  # tenant's own bot: customer routes only
        return handle_customer_bot(ctx, user_id=str(user_id))
    user_role = effective_role(is_platform_admin=bool(ctx.is_admin), roles=ctx.roles)
    scope = policy_scope(ctx)
    legacy_prices = build_legacy_prices(default_price_rub=default_price_rub, tenant_id=scope.tenant_id, product_id=scope.product_id if scope.has_product else '')

    def pm(*, text: str, reply_markup: dict | None = None, track_event_type: str | None = None, track_payload: dict | None = None) -> ProposedAction:
        return propose_message(user_id=user_id, text=text, reply_markup=reply_markup, callback_query_id=ctx.callback_query_id, track_event_type=track_event_type, track_payload=track_payload)

    denied = _rbac_denial(ctx)
    if denied is not None:
        return pm(text=denied, reply_markup=kb_back_main())

    for handler in (
        lambda: handle_offer_outcome(ctx, user_id=user_id, default_price_rub=default_price_rub),
        lambda: handle_ads_apply_flow(ctx, user_id=user_id),
        lambda: handle_ads_apply(ctx, user_id=user_id) if str(ctx.callback_data or "").startswith("ads:apply:") else None,
        lambda: handle_autopilot(ctx, user_id=user_id, default_price_rub=default_price_rub),
        lambda: handle_ai_ceo(ctx, user_id=user_id),
        lambda: handle_growth_strategy(ctx, user_id=user_id),
        lambda: handle_sales_buttons(ctx, user_id=str(user_id)),
        lambda: handle_gift(ctx, user_id=user_id, bot_username=bot_username, gift_ttl_sec=gift_ttl_sec, pm=pm),
        lambda: handle_admin_pricing_session(ctx, user_id=user_id, pm=lambda text, reply_markup=None, track_event_type=None, track_payload=None: pm(text=text, reply_markup=reply_markup, track_event_type=track_event_type, track_payload=track_payload)),
    ):
        out = handler()
        if out is not None:
            return out

    from core.policies.telegram.routes.business_flow_routes import handle_clientplatform_callbacks
    callback_outcome = handle_clientplatform_callbacks(ctx, user_id=str(user_id), pm=pm)
    if callback_outcome is not None:
        return callback_outcome

    if ctx.cmd == "/start" and str(ctx.args or "").strip().startswith(("cpa_", "ecv_")):
        from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
        return handle_business_flow_routes(ctx, user_id=str(user_id))
    if ctx.cmd in {"/start", "/menu"} or ctx.callback_data in {CB_MENU_MAIN, "menu_main"}:
        variant = choose_marketing_variant(user_id=str(user_id), step_key="menu_main", seed=str(ctx.marketing_seed or "1"), bandit=(ctx.marketing_bandit or {}).get("menu_main"))
        msg = menu_text(role=user_role, is_admin=ctx.is_admin)
        return pm(text=msg, reply_markup=kb_main(is_admin=ctx.is_admin, role=user_role), track_event_type="marketing_copy_chosen", track_payload={"step_key": "menu_main", "variant": variant})

    if ctx.callback_data == "full":
        if ctx.full_access:
            return pm(text="Полный доступ уже активен ✅", reply_markup=kb_back_main())
        from core.policies.telegram.tariffs import propose_show_tariffs
        return propose_show_tariffs(user_id=user_id, legacy_prices=legacy_prices, marketing_variants=ctx.marketing_variants, marketing_seed=ctx.marketing_seed, marketing_bandit=ctx.marketing_bandit, pricing_suggestions=getattr(ctx, 'pricing_suggestions', None), plans=scoped_active_plans(ctx))

    for grouped in (
        lambda: handle_settings_routes(ctx, user_id=user_id, bot_username=bot_username, pm=pm),
        lambda: handle_command_routes(ctx, user_id=user_id, pm=pm),
        lambda: handle_admin(ctx, user_id=str(user_id), pm=pm),
        lambda: handle_marketing_routes(ctx, user_id=user_id, default_price_rub=default_price_rub, legacy_prices=legacy_prices, bot_username=bot_username, pm=pm),
    ):
        out = grouped()
        if out is not None:
            return out

    if ctx.callback_data:
        return pm(text="Этот раздел пока недоступен в Telegram. Вернись в главное меню.", reply_markup=kb_back_main())

    msg = ("Рабочее пространство подключено. Выберите раздел меню или опишите бизнес-задачу."
           if ctx.full_access else
           "Опишите задачу бизнеса или выберите раздел в меню. Доступные тарифы — в разделе «Оплаты и тарифы».")
    result = handle_free_text(
        ctx, user_id=str(user_id), msg=msg,
        rerun=lambda updated: handle(
            updated, default_price_rub=default_price_rub, bot_username=bot_username,
            gift_ttl_sec=gift_ttl_sec,
        ),
    )
    if result is not None:
        return result
    return pm(text=msg, reply_markup=kb_main(is_admin=ctx.is_admin, role=user_role))



def _rbac_denial(ctx: TelegramCtx) -> str | None:
    permission = required_permission(
        callback_data=str(ctx.callback_data or ""), cmd=str(ctx.cmd or ""),
    )
    if permission is None or has_permission(ctx, permission):
        return None
    return "Для этого раздела требуется подтверждённая роль владельца или сотрудника."
