from __future__ import annotations

"""Autopilot and growth-related keyboards."""

from typing import Any

from core.users.roles import UserRoleInfo
from core.ux.callbacks import (
    CB_ADS_APPLY_CANCEL,
    CB_ADS_APPLY_CONFIRM,
    CB_ADS_APPLY_MENU,
    CB_ADS_APPLY_PREVIEW,
    CB_AUTOPILOT_DASHBOARD_AUTOPILOT,
    CB_AUTOPILOT_DASHBOARD_TASKS,
    CB_AUTOPILOT_DASHBOARD_TODAY,
    CB_AUTOPILOT_MENU,
    CB_GROWTH_BACKLOG,
    CB_GROWTH_GENERATE,
    CB_MENU_MAIN,
    CB_PROFIT_SPRINT_LEAD_ADS,
    CB_PROFIT_SPRINT_LEAD_CALLS,
    CB_PROFIT_SPRINT_LEAD_INBOX,
    CB_PROFIT_SPRINT_LEAD_SITE,
    CB_PROFIT_SPRINT_LEAD_SOCIAL,
    CB_PROFIT_SPRINT_START,
)

from .common import mk


def kb_autopilot_menu(*, role: UserRoleInfo | None = None) -> dict[str, Any]:
    r = (role or UserRoleInfo("owner")).role
    rows: list[list[dict[str, str]]] = []
    if r in ("owner", "operator"):
        rows.append([{"text": "🚀 Запустить: +прибыль за 7 дней", "callback_data": CB_PROFIT_SPRINT_START}])
    rows.extend(
        [
            [{"text": "📊 Дашборд (сегодня)", "callback_data": CB_AUTOPILOT_DASHBOARD_TODAY}],
            [{"text": "🤖 Что сделал автопилот", "callback_data": CB_AUTOPILOT_DASHBOARD_AUTOPILOT}],
            [{"text": "✅ Что делать мне", "callback_data": CB_AUTOPILOT_DASHBOARD_TASKS}],
        ]
    )
    if r == "marketer":
        rows.insert(0, [{"text": "🧩 Ads Apply (prod)", "callback_data": CB_ADS_APPLY_MENU}])
    rows.append([{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}])
    return mk(rows)


def kb_profit_sprint_lead_sources() -> dict[str, Any]:
    return mk(
        [
            [{"text": "Входящие сообщения", "callback_data": CB_PROFIT_SPRINT_LEAD_INBOX}],
            [{"text": "Звонки", "callback_data": CB_PROFIT_SPRINT_LEAD_CALLS}],
            [{"text": "Сайт / формы", "callback_data": CB_PROFIT_SPRINT_LEAD_SITE}],
            [{"text": "Соцсети", "callback_data": CB_PROFIT_SPRINT_LEAD_SOCIAL}],
            [{"text": "Реклама", "callback_data": CB_PROFIT_SPRINT_LEAD_ADS}],
        ]
    )


def kb_ads_apply_pending(*, can_apply: bool = True) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = [
        [{"text": "👀 Предпросмотр плана", "callback_data": CB_ADS_APPLY_PREVIEW}],
    ]
    if can_apply:
        rows.append([{"text": "✅ Применить (подтвердить)", "callback_data": CB_ADS_APPLY_CONFIRM}])
    else:
        rows.append([{"text": "🛑 Применение выключено", "callback_data": CB_ADS_APPLY_MENU}])
    rows.append([{"text": "✖️ Отмена", "callback_data": CB_ADS_APPLY_CANCEL}])
    rows.append([{"text": "⬅️ Назад", "callback_data": CB_AUTOPILOT_MENU}])
    return mk(rows)


def kb_growth_menu() -> dict[str, Any]:
    return mk(
        [
            [{"text": "🔁 Сгенерировать backlog", "callback_data": CB_GROWTH_GENERATE}],
            [{"text": "📋 Посмотреть backlog", "callback_data": CB_GROWTH_BACKLOG}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )
