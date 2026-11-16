"""ClientPlatform Telegram settings navigation via the canonical BusinessAIOS owner cockpit."""
from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.callbacks import CB_SETTINGS_MENU, CB_SETTINGS_STATE
from core.ux.telegram_keyboards import kb_back_main, kb_settings_menu

# These existing cockpit screens perform the authorized projections through
# business_ops_summary@v1. No secondary settings store or execution path.
_CANONICAL_SCREENS = {
    "cp:settings:access": "cpm:team:0",
}
_LEGACY_CALLBACK_PREFIXES = ("settings:time:", "settings:ref", "state:", "weather:", "demo")
_LEGACY_COMMANDS = {"/time_work", "/time_home"}


_ORG_OPS = {
    "cp:settings:organization": "organization_show",
    "/org_create": "organization_create",
    "/org_name": "organization_name",
    "/org_type": "organization_type",
}
_NOTIFICATION_OPS = {
    "cp:settings:notifications": "notifications_show",
    "cp:settings:notifications:toggle": "notifications_toggle",
    "cp:settings:notifications:level": "notifications_level",
}


def handle_settings_routes(ctx: TelegramCtx, *, user_id: str, bot_username: str, pm) -> ProposedAction | None:
    if ctx.callback_data == CB_SETTINGS_MENU:
        return pm(text="⚙️ Настройки ClientPlatform\n\nВыберите раздел:", reply_markup=kb_settings_menu())
    organization_op = _ORG_OPS.get(ctx.callback_data) or _ORG_OPS.get(ctx.cmd)
    notification_op = _NOTIFICATION_OPS.get(ctx.callback_data)
    if organization_op or notification_op:
        if not ctx.is_admin:
            return pm(text="Настройки организации и служебных оповещений доступны администратору бизнеса.",
                      reply_markup=kb_back_main())
        args = {"user_id": user_id, "op": organization_op or notification_op, "arg": ""}
        if organization_op:
            state = getattr(ctx, "state", None)
            session = getattr(state, "session", None)
            session = session if isinstance(session, dict) else {}
            selected = str(session.get("selected_business_id") or "").strip()
            bound = str(session.get("business_id") or "").strip()
            if selected and bound and selected != bound:
                return pm(text="Контекст бизнеса изменился. Выберите бизнес заново, чтобы открыть правильную организацию.",
                          reply_markup=kb_back_main())
            business_id = selected or bound
            if not business_id:
                return pm(text="Сначала выберите бизнес. Без подтверждённого выбора карточка организации не открывается.",
                          reply_markup=kb_back_main())
            args["business_id"] = business_id
            if organization_op != "organization_show":
                args["arg"] = str(ctx.args or "").strip()[:300]
        if ctx.callback_query_id:
            args["callback_query_id"] = ctx.callback_query_id
        return propose("business_admin@v1", args)
    if ctx.callback_data in _CANONICAL_SCREENS:
        if not ctx.is_admin:
            return pm(text="Управление доступно только администратору.", reply_markup=kb_back_main())
        payload = {"user_id": user_id, "op": "cockpit", "arg": _CANONICAL_SCREENS[ctx.callback_data]}
        if ctx.callback_query_id:
            payload["callback_query_id"] = ctx.callback_query_id
        return propose("business_ops_summary@v1", payload)
    if (ctx.callback_data in {CB_SETTINGS_STATE, "settings:state"}
            or ctx.callback_data.startswith(_LEGACY_CALLBACK_PREFIXES)
            or ctx.cmd in _LEGACY_COMMANDS):
        return pm(text="Эта функция не относится к бизнес-платформе. Откройте актуальное меню.", reply_markup=kb_back_main())
    return None
