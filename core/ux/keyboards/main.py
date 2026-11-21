"""Canonical Telegram main keyboard facade backed by unified ClientPlatform UI."""
from __future__ import annotations

from typing import Any

from core.users.roles import UserRoleInfo
from core.ux.callbacks import CB_MENU_MAIN
from core.ux.keyboards.common import mk


def kb_main(*, is_admin: bool = False, role: UserRoleInfo | str | None = None) -> dict[str, Any]:
    from core.ux.unified_messenger_menu import telegram_menu

    normalized_role = role.role if isinstance(role, UserRoleInfo) else str(role or "guest")
    return telegram_menu(role=normalized_role, is_admin=is_admin)


def kb_back_main() -> dict[str, Any]:
    return mk([[{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}]])
