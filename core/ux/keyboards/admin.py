from __future__ import annotations

"""Admin and staff keyboards."""

from typing import Any, Dict

from core.ux.callbacks import CB_MENU_MAIN

from .common import mk


def kb_staff_menu() -> Dict[str, Any]:
    return mk(
        [
            [{"text": "📊 Сводка (кратко)", "callback_data": "admin:demo:brief"}],
            [{"text": "📈 Сводка (подробно)", "callback_data": "admin:demo:full"}],
            [{"text": "👥 Пользователи сегодня", "callback_data": "admin:users:today"}],
            [{"text": "🔎 Карточка пользователя", "callback_data": "admin:user:card"}],
            [{"text": "🧠 Поведение", "callback_data": "admin:behavior"}],
            [{"text": "⏱ Латентность кнопок", "callback_data": "admin:latency"}],
            [{"text": "📉 Воронка", "callback_data": "admin:funnel"}],
            [{"text": "💰 Конверсия", "callback_data": "admin:conversion"}],
            [{"text": "🧲 Сегменты", "callback_data": "admin:segments"}],
            [{"text": "🧪 Тесты офферов", "callback_data": "admin:ab"}],
            [{"text": "🤖 ИИ-копирайтер", "callback_data": "admin:copy:menu"}],
            [{"text": "🧬 Эволюция: регенерация копирайта", "callback_data": "admin:evolution:regen_copy"}],
            [{"text": "🤖 ИИ-цены (рекомендации)", "callback_data": "admin:ai:prices"}],
            [{"text": "👥 Роли команды", "callback_data": "admin:roles:menu"}],
            [{"text": "🔐 Доступы админов", "callback_data": "admin:perms"}],
            [{"text": "💳 Тарифы", "callback_data": "admin:tariffs:show"}],
            [{"text": "💸 Изменить цены (governed)", "callback_data": "admin:pricing:menu"}],
            [{"text": "🧾 История тарифов", "callback_data": "admin:tariffs:history"}],
            [{"text": "🎁 Подарки и рекомендации", "callback_data": "admin:giftshare"}],
            [{"text": "🧲 Воронка 2.0", "callback_data": "admin:funnel2"}],
            [{"text": "🧩 Удержание", "callback_data": "admin:retention"}],
            [{"text": "🧾 Мои состояния (10)", "callback_data": "admin:state:last"}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )
