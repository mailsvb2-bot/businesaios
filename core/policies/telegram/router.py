from __future__ import annotations

from typing import Dict

from core.policies.telegram.context import TelegramCtx
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
from core.policies.telegram.routes.command_routes import handle_command_routes
from core.policies.telegram.routes.marketing_routes import handle_marketing_routes
from core.policies.telegram.routes.settings_routes import handle_settings_routes
from core.users.roles import UserRoleInfo
from core.ux.callbacks import CB_MENU_MAIN
from core.ux.telegram_keyboards import kb_back_main, kb_main, kb_settings_menu


def _has_perm(ctx: TelegramCtx, perm: str) -> bool:
    if bool(getattr(ctx, "is_superadmin", False)):
        return True
    perms = {str(x) for x in (getattr(ctx, "perms", []) or [])}
    roles = {str(x) for x in (getattr(ctx, "roles", []) or [])}
    return (str(perm) in perms) or ("admin" in roles)


def handle(ctx: TelegramCtx, *, default_price_rub: int, bot_username: str = "", gift_ttl_sec: int = 7 * 24 * 3600) -> ProposedAction:
    user_id = ctx.state.user_id or "anonymous"
    _ = UserRoleInfo.from_settings(ctx.settings if isinstance(ctx.settings, dict) else {})
    legacy_prices = build_legacy_prices(default_price_rub=default_price_rub)

    def pm(*, text: str, reply_markup: dict | None = None, track_event_type: str | None = None, track_payload: dict | None = None) -> ProposedAction:
        return propose_message(user_id=user_id, text=text, reply_markup=reply_markup, callback_query_id=ctx.callback_query_id, track_event_type=track_event_type, track_payload=track_payload)

    for handler in (
        lambda: handle_offer_outcome(ctx, user_id=user_id, default_price_rub=default_price_rub),
        lambda: handle_ads_apply_flow(ctx, user_id=user_id),
        lambda: handle_ads_apply(ctx, user_id=user_id) if str(ctx.callback_data or "").startswith("ads:apply:") else None,
        lambda: handle_autopilot(ctx, user_id=user_id, default_price_rub=default_price_rub),
        lambda: handle_ai_ceo(ctx, user_id=user_id),
        lambda: handle_growth_strategy(ctx, user_id=user_id),
        lambda: handle_gift(ctx, user_id=user_id, bot_username=bot_username, gift_ttl_sec=gift_ttl_sec, pm=pm),
        lambda: handle_admin_pricing_session(ctx, user_id=user_id, pm=lambda text, reply_markup=None, track_event_type=None, track_payload=None: pm(text=text, reply_markup=reply_markup, track_event_type=track_event_type, track_payload=track_payload)),
    ):
        out = handler()
        if out is not None:
            return out

    if ctx.cmd in {"/start", "/menu"} or ctx.callback_data in {CB_MENU_MAIN, "menu_main"}:
        step = "menu_main"
        variant = choose_marketing_variant(user_id=str(user_id), step_key=step, seed=str(ctx.marketing_seed or "1"), bandit=(ctx.marketing_bandit or {}).get(step))
        variants = (ctx.marketing_variants or {}).get(step) or {}
        msg = str(variants.get(variant) or variants.get("a") or variants.get("b") or ("BusinesAIOS Workspace: переобучение нервной системы через ритм повседневности.\n\nГлавное меню — выбери, что сейчас нужно:"))
        return pm(text=msg, reply_markup=kb_main(is_admin=ctx.is_admin), track_event_type="marketing_copy_chosen", track_payload={"step_key": step, "variant": variant})

    if ctx.callback_data == "full":
        if ctx.full_access:
            return pm(text="Полный доступ уже активен ✅", reply_markup=kb_back_main())
        from core.policies.telegram.tariffs import propose_show_tariffs
        return propose_show_tariffs(user_id=user_id, legacy_prices=legacy_prices, marketing_variants=ctx.marketing_variants, marketing_seed=ctx.marketing_seed, marketing_bandit=ctx.marketing_bandit, pricing_suggestions=getattr(ctx, 'pricing_suggestions', None))

    for grouped in (
        lambda: handle_settings_routes(ctx, user_id=user_id, bot_username=bot_username, pm=pm),
        lambda: handle_command_routes(ctx, user_id=user_id, pm=pm),
        lambda: handle_admin(ctx, user_id=str(user_id), pm=pm),
        lambda: handle_marketing_routes(ctx, user_id=user_id, default_price_rub=default_price_rub, legacy_prices=legacy_prices, bot_username=bot_username, pm=pm),
    ):
        out = grouped()
        if out is not None:
            return out

    if ctx.full_access:
        msg = "Я здесь. Напиши, что сейчас происходит в твоём дне — и мы настроим ритм."
    else:
        msg = "Я здесь. Напиши, что сейчас происходит. Если нужен полный доступ — /pay или кнопка «Полный доступ»."
    return pm(text=msg, reply_markup=kb_main(is_admin=ctx.is_admin))
