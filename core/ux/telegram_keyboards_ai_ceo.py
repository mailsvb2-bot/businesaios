from __future__ import annotations

from core.ux.callbacks import CB_AUTOPILOT_MENU, CB_CEO_MENU, CB_CEO_PLAN, CB_CEO_RUN, CB_GROWTH_MENU


def kb_ai_ceo_menu(*, can_run: bool) -> dict:
    btns = [[{"text": "🔄 Обновить план", "callback_data": CB_CEO_PLAN}]]
    if can_run:
        btns.append([{"text": "🛡 Проверить готовность запуска", "callback_data": CB_CEO_RUN}])
    btns.append([{"text": "⬅️ В меню", "callback_data": CB_MENU_MAIN}])
    return {"inline_keyboard": btns}


def ai_section_rows(*, analytics: bool) -> list[list[dict]]:
    """Entries of the «ИИ и автопилот» section that lead to existing owners."""
    if not analytics:
        return []
    return [[{"text": "🧠 ИИ-директор: план", "callback_data": CB_CEO_MENU}],
            [{"text": "📈 Стратегия роста: гипотезы", "callback_data": CB_GROWTH_MENU}]]
