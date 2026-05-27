from __future__ import annotations

"""Settings, state, demo and weather keyboards."""

from typing import Any, Dict, List

from core.ux.callbacks import CB_MENU_MAIN

from .common import mk


def kb_demo_kind() -> Dict[str, Any]:
    return mk(
        [
            [{"text": "⏰ Утро", "callback_data": "demo_kind_work"}],
            [{"text": "🌙 Вечер", "callback_data": "demo_kind_home"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_weather() -> Dict[str, Any]:
    return mk(
        [
            [{"text": "🏙 Изменить город", "callback_data": "weather:city"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_settings_menu() -> Dict[str, Any]:
    return mk(
        [
            [{"text": "⏰ Время (утро)", "callback_data": "settings:time:work"}],
            [{"text": "🌙 Время (вечер)", "callback_data": "settings:time:home"}],
            [{"text": "🔗 Реф. ссылка", "callback_data": "settings:ref"}],
            [{"text": "📈 Состояния", "callback_data": "settings:state"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_state_menu() -> Dict[str, Any]:
    return mk(
        [
            [{"text": "⭐ Оценить состояние", "callback_data": "state:rate"}],
            [{"text": "📅 Сегодня", "callback_data": "state:today"}],
            [{"text": "📅 Вчера", "callback_data": "state:yesterday"}],
            [{"text": "📚 Все", "callback_data": "state:all"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_mood_rate() -> Dict[str, Any]:
    row1 = [{"text": str(i), "callback_data": f"state:rate:{i}"} for i in range(0, 6)]
    row2 = [{"text": str(i), "callback_data": f"state:rate:{i}"} for i in range(6, 11)]
    return mk([row1, row2, [{"text": "⬅️ Назад", "callback_data": "settings:state"}]])
