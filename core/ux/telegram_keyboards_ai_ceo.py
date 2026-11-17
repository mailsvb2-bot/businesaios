from __future__ import annotations

from core.ux.callbacks import CB_AUTOPILOT_MENU, CB_CEO_MENU, CB_CEO_PLAN, CB_CEO_RUN


def kb_ai_ceo_menu(*, can_run: bool) -> dict:
    btns = [[{"text": "🔄 Обновить план", "callback_data": CB_CEO_PLAN}]]
    if can_run:
        btns.append([{"text": "🛡 Проверить готовность запуска", "callback_data": CB_CEO_RUN}])
    btns.append([{"text": "⬅️ В меню", "callback_data": CB_MENU_MAIN}])
    return {"inline_keyboard": btns}


def ai_section_rows(*, analytics: bool) -> list[list[dict]]:
    """Entries of the «ИИ и автопилот» section that lead to existing owners."""
    return [[{"text": "🧠 ИИ-директор: план", "callback_data": CB_CEO_MENU}]] if analytics else []
