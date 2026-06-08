from __future__ import annotations

from core.ux.callbacks import CB_CEO_PLAN, CB_CEO_RUN, CB_MENU_MAIN


def kb_ai_ceo_menu(*, can_run: bool) -> dict:
    btns = [[{"text": "🔄 Обновить план", "callback_data": CB_CEO_PLAN}]]
    if can_run:
        btns.append([{"text": "🚀 Выполнить (execute_plan)", "callback_data": CB_CEO_RUN}])
    btns.append([{"text": "⬅️ В меню", "callback_data": CB_MENU_MAIN}])
    return {"inline_keyboard": btns}
