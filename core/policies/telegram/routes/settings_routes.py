"""ClientPlatform Telegram settings navigation via the canonical BusinessAIOS owner cockpit."""
from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.callbacks import CB_SETTINGS_MENU, CB_SETTINGS_STATE
from core.ux.telegram_keyboards import kb_back_main, kb_settings_menu

# These existing cockpit screens perform the authorized projections through
# business_ops_summary@v1. No secondary settings store or execution path.
_CANONICAL_SCREENS = {
    "cp:settings:organization": "cpm:manage",
    "cp:settings:notifications": "cpm:automation",
    "cp:settings:access": "cpm:team:0",
}
_LEGACY_CALLBACK_PREFIXES = ("settings:time:", "settings:ref", "state:")
_LEGACY_COMMANDS = {"/time_work", "/time_home"}


def handle_settings_routes(ctx: TelegramCtx, *, user_id: str, bot_username: str, pm) -> ProposedAction | None:
    if ctx.callback_data == CB_SETTINGS_MENU:
        return pm(text="⚙️ Настройки ClientPlatform\n\nВыберите раздел:", reply_markup=kb_settings_menu())
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
