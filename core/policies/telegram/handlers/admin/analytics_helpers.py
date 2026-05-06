from __future__ import annotations

from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def deny_if_not_admin(is_admin: bool, *, pm):
    if not is_admin:
        return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
    return None


def staff_reply(*, pm, text: str):
    return pm(text=text, reply_markup=kb_staff_menu())
