from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu

ROLE_PERM_COMMANDS = {"/role_add", "/role_del", "/perm_add", "/perm_del"}


def handle_roles_perms(ctx: TelegramCtx, *, user_id: str, pm) -> ProposedAction | None:
    if ctx.cmd not in ROLE_PERM_COMMANDS and ctx.callback_data != "admin:roles:menu":
        return None

    if not ctx.is_admin:
        return pm(text="Доступ запрещён.", reply_markup=kb_back_main())

    if ctx.callback_data == "admin:roles:menu":
        txt = (
            "👥 Роли команды\n\n"
            "Роли задаются событиями (канонично, без правки кода в рантайме).\n\n"
            "Команды:\n"
            "• /role_add <user_id> <role>  (role: admin|marketing)\n"
            "• /role_del <user_id> <role>\n\n"
            "• /perm_add <user_id> <perm>\n"
            "• /perm_del <user_id> <perm>\n"
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    parts = (ctx.args or "").split()
    if len(parts) < 2:
        return pm(
            text="Формат: /role_add <user_id> <role> (или /perm_add <user_id> <perm>)",
            reply_markup=kb_staff_menu(),
        )

    target = parts[0].strip()
    item = " ".join(parts[1:]).strip()
    if not target.isdigit() or not item:
        return pm(text="Некорректные параметры.", reply_markup=kb_staff_menu())

    enabled = ctx.cmd in {"/role_add", "/perm_add"}
    if ctx.cmd.startswith("/role_"):
        return propose(
            "admin_set_role@v1",
            {
                "admin_id": user_id,
                "target_user_id": str(target),
                "role": str(item),
                "enabled": bool(enabled),
                "notify_text": f"✅ Роль {'добавлена' if enabled else 'удалена'}: {item} для {target}",
                "notify_reply_markup": kb_staff_menu(),
                "callback_query_id": ctx.callback_query_id,
            },
        )

    return propose(
        "admin_set_perm@v1",
        {
            "admin_id": user_id,
            "target_user_id": str(target),
            "perm": str(item),
            "enabled": bool(enabled),
            "notify_text": f"✅ Доступ {'добавлен' if enabled else 'удален'}: {item} для {target}",
            "notify_reply_markup": kb_staff_menu(),
            "callback_query_id": ctx.callback_query_id,
        },
    )
