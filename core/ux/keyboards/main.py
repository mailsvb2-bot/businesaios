"""Main and navigation keyboards."""

from __future__ import annotations

from typing import Any

from core.users.roles import UserRoleInfo
from core.ux.callbacks import (
    CB_ADMIN_MENU,
    CB_ADS_APPLY_MENU,
    CB_AUTOPILOT_DASHBOARD_TODAY,
    CB_AUTOPILOT_MENU,
    CB_DEMO,
    CB_GIFT_MENU,
    CB_GROWTH_MENU,
    CB_MENU_MAIN,
    CB_SETTINGS_MENU,
    CB_SETTINGS_STATE,
    CB_SHARE_MENU,
    CB_SUB_MENU,
    CB_WEATHER_SHOW,
)

from .common import mk


def kb_main(*, is_admin: bool = False, role: UserRoleInfo | None = None) -> dict[str, Any]:
    """Unified ClientPlatform navigation; existing canonical callbacks stay stable."""
    from core.ux.clientplatform_unified_menu import telegram_menu

    normalized_role = (role or UserRoleInfo("owner")).role
    return telegram_menu(role=normalized_role, is_admin=is_admin)


def kb_back_main() -> dict[str, Any]:
    return mk([[{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}]])
