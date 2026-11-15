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


def handle_settings_routes(ctx: TelegramCtx, *, user_id: str, bot_username: str, pm) -> ProposedAction | None:
    if ctx.callback_data == CB_SETTINGS_MENU:
        return pm(text="⚙️ Настройки ClientPlatform\n\nВыберите раздел:", reply_markup=kb_settings_menu())
    organization_ops = {
        "cp:settings:organization": "organization_show",
        "/org_create": "organization_create",
        "/org_name": "organization_name",
        "/org_type": "organization_type",
    }
    operation = organization_ops.get(ctx.callback_data) or organization_ops.get(ctx.cmd)
    if operation:
        if not ctx.is_admin:
            return pm(text="Карточка организации доступна только администратору бизнеса.", reply_markup=kb_back_main())
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
        return propose("business_admin@v1", {
            "user_id": user_id, "business_id": business_id, "op": operation,
            "arg": str(ctx.args or "").strip()[:300] if operation != "organization_show" else "",
            **({"callback_query_id": ctx.callback_query_id} if ctx.callback_query_id else {}),
        })
    notification_ops = {
        "cp:settings:notifications": "notifications_show",
        "cp:settings:notifications:toggle": "notifications_toggle",
        "cp:settings:notifications:level": "notifications_level",
    }
    if ctx.callback_data in notification_ops:
        if not ctx.is_admin:
            return pm(text="Настройки служебных оповещений доступны администратору бизнеса.", reply_markup=kb_back_main())
        return propose("business_admin@v1", {
            "user_id": user_id, "op": notification_ops[ctx.callback_data], "arg": "",
            **({"callback_query_id": ctx.callback_query_id} if ctx.callback_query_id else {}),
        })
    if ctx.callback_data in _CANONICAL_SCREENS:
        if not ctx.is_admin:
            return pm(text="Управление доступно только администратору.", reply_markup=kb_back_main())
        cbq = str(getattr(ctx, "callback_query_id", "") or "").strip()
        payload = {"user_id": user_id, "op": "cockpit", "arg": _CANONICAL_SCREENS[ctx.callback_data]}
        if cbq:
            payload["callback_query_id"] = cbq
        return propose("business_ops_summary@v1", payload)
    if (ctx.callback_data in {CB_SETTINGS_STATE, "settings:state"}
            or ctx.callback_data.startswith(_LEGACY_CALLBACK_PREFIXES)
            or ctx.cmd in _LEGACY_COMMANDS):
        return pm(text="Эта функция не относится к бизнес-платформе. Откройте актуальное меню.", reply_markup=kb_back_main())
    return None
