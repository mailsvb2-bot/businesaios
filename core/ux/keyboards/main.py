from __future__ import annotations

"""Main and navigation keyboards."""

from typing import Any, Dict, List

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
    r = (role or UserRoleInfo("owner")).role
    rows: list[list[dict[str, str]]] = [
        [
            {"text": "🎧 Демо", "callback_data": CB_DEMO},
            {"text": "🔐 Полный доступ", "callback_data": "full"},
        ],
        [{"text": "🚀 Автопилот: +прибыль за 7 дней", "callback_data": CB_AUTOPILOT_MENU}],
        [{"text": "🧠 AI Growth Strategy", "callback_data": CB_GROWTH_MENU}],
        [
            {"text": "💳 Тарифы", "callback_data": CB_SUB_MENU},
            {"text": "🎁 Подарить", "callback_data": CB_GIFT_MENU},
        ],
        [
            {"text": "🧠 Настройки", "callback_data": CB_SETTINGS_MENU},
            {"text": "📈 Анализ", "callback_data": CB_SETTINGS_STATE},
        ],
        [
            {"text": "📣 Посоветовать", "callback_data": CB_SHARE_MENU},
            {"text": "🌤 Погода", "callback_data": CB_WEATHER_SHOW},
        ],
    ]
    if r in ("marketer", "operator"):
        rows.insert(2, [{"text": "🧩 Ads Apply (prod)", "callback_data": CB_ADS_APPLY_MENU}])
    if r == "operator":
        rows.insert(2, [{"text": "📊 Сегодня: KPI", "callback_data": CB_AUTOPILOT_DASHBOARD_TODAY}])
    if is_admin:
        rows.append([{"text": "🛠 Панель", "callback_data": CB_ADMIN_MENU}])
    return mk(rows)


def kb_back_main() -> dict[str, Any]:
    return mk([[{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}]])
