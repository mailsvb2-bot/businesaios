"""Business settings route; legacy therapy callbacks fail closed."""
from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.ux.callbacks import CB_SETTINGS_MENU, CB_SETTINGS_STATE
from core.ux.telegram_keyboards import kb_back_main, kb_settings_menu

_BUSINESS_SETTINGS = {
    "cp:settings:organization": "🏢 Организация\\n\\nУправление организацией доступно в рабочем пространстве.",
    "cp:settings:notifications": "🔔 Уведомления\\n\\nУправляйте уведомлениями в рабочем пространстве.",
    "cp:settings:access": "🔐 Доступ и права\\n\\nНастройка ролей выполняется через администрирование.",
}
_LEGACY_CALLBACK_PREFIXES = ("settings:time:", "settings:ref", "state:")
_LEGACY_COMMANDS = {"/time_work", "/time_home"}


def handle_settings_routes(ctx: TelegramCtx, *, user_id: str, bot_username: str, pm) -> ProposedAction | None:
    if ctx.callback_data == CB_SETTINGS_MENU:
        return pm(text="⚙️ Настройки BusinessAIOS\\n\\nВыберите раздел:", reply_markup=kb_settings_menu())
    if ctx.callback_data in _BUSINESS_SETTINGS:
        return pm(text=_BUSINESS_SETTINGS[ctx.callback_data], reply_markup=kb_settings_menu())
    if (ctx.callback_data in {CB_SETTINGS_STATE, "settings:state"}
            or ctx.callback_data.startswith(_LEGACY_CALLBACK_PREFIXES)
            or ctx.cmd in _LEGACY_COMMANDS):
        return pm(text="Эта функция не относится к бизнес-платформе. Откройте актуальное меню.", reply_markup=kb_back_main())
    return None
