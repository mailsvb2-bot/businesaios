from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.ux.callbacks import CB_ADMIN_MENU
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def handle_admin_menu(ctx: TelegramCtx, *, pm) -> ProposedAction | None:
    if ctx.callback_data != CB_ADMIN_MENU:
        return None
    if not ctx.is_admin:
        return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
    return pm(
        text=(
            "🛠 Админ\n\n"
            "Выбери раздел.\n"
            "Подсказка: можно пользоваться и командами: /admin /demo_stats /funnel /retention"
        ),
        reply_markup=kb_staff_menu(),
        track_event_type="admin_panel_opened",
    )
