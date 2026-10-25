"""Settings, state, demo and weather keyboards."""

from __future__ import annotations

from typing import Any

from core.ux.callbacks import CB_MENU_MAIN

from .common import mk


def kb_demo_kind() -> dict[str, Any]:
    return mk(
        [
            [{"text": "⏰ Утро", "callback_data": "demo_kind_work"}],
            [{"text": "🌙 Вечер", "callback_data": "demo_kind_home"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_weather() -> dict[str, Any]:
    return mk(
        [
            [{"text": "🏙 Изменить город", "callback_data": "weather:city"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_settings_menu() -> dict[str, Any]:
    """Organization-only settings: no therapy schedules or mood tracking."""
    return mk([
        [{"text": "🏢 Организация", "callback_data": "cp:settings:organization"}],
        [{"text": "🔔 Уведомления", "callback_data": "cp:settings:notifications"}],
        [{"text": "🔐 Доступ и права", "callback_data": "cp:settings:access"}],
        [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
    ])


def kb_state_menu() -> dict[str, Any]:
    return mk(
        [
            [{"text": "⭐ Оценить состояние", "callback_data": "state:rate"}],
            [{"text": "📅 Сегодня", "callback_data": "state:today"}],
            [{"text": "📅 Вчера", "callback_data": "state:yesterday"}],
            [{"text": "📚 Все", "callback_data": "state:all"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_mood_rate() -> dict[str, Any]:
    row1 = [{"text": str(i), "callback_data": f"state:rate:{i}"} for i in range(0, 6)]
    row2 = [{"text": str(i), "callback_data": f"state:rate:{i}"} for i in range(6, 11)]
    return mk([row1, row2, [{"text": "⬅️ Назад", "callback_data": "settings:state"}]])
