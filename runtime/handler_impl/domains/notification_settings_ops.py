"""Telegram adapter to the existing tenant-scoped alert subscription setting.

The canonical EventStore settings gateway owns persistence. This module does not
create a second notification store or send notifications itself.
"""
from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY
from runtime.messaging_policy_alert_subscriptions.settings_value_builder import canonical_alert_subscriptions_value
from runtime.settings.event_store_gateway import build_event_store_settings_gateway


def notification_preferences(*, event_store, tenant_id: str, user_id: str, operation: str) -> tuple[str, dict]:
    if operation not in {"notifications_show", "notifications_toggle", "notifications_level"}:
        raise ValueError("unsupported notification operation")
    gateway = build_event_store_settings_gateway(event_store=event_store)
    level_order = ("info", "warn", "critical")

    def selected(value):
        entries = canonical_alert_subscriptions_value(value, tenant_id=tenant_id)
        own = next((item for item in entries if item["recipient_user_id"] == user_id
                    and item["channel"] == "telegram" and not item["business_id"]), None)
        return entries, own

    if operation != "notifications_show":
        for _ in range(3):
            before = gateway.get_value(tenant_id=tenant_id, key=SETTING_KEY)
            entries, own = selected(before)
            current = own or {"recipient_user_id": user_id, "channel": "telegram",
                              "business_id": "", "enabled": False, "min_level": "warn",
                              "code_filters": [], "user_scope": []}
            updated = dict(current)
            if operation == "notifications_toggle":
                updated["enabled"] = not bool(current["enabled"])
            else:
                level = str(current["min_level"])
                updated["min_level"] = level_order[(level_order.index(level) + 1) % len(level_order)]
            entries = [item for item in entries if not (
                item["recipient_user_id"] == user_id and item["channel"] == "telegram"
                and not item["business_id"])]
            entries.append(updated)
            if gateway.compare_and_set_value(tenant_id=tenant_id, key=SETTING_KEY,
                                             expected=before, value=entries):
                break
        else:
            raise RuntimeError("notification_preferences_concurrent_change")
    after = gateway.get_value(tenant_id=tenant_id, key=SETTING_KEY)
    _, own = selected(after)
    enabled = bool(own and own["enabled"])
    level = own["min_level"] if own else "warn"
    text = ("🔔 Системные уведомления\n\n"
            f"Получатель: ваш Telegram-аккаунт\n"
            f"Оповещения: {'включены' if enabled else 'выключены'}\n"
            f"Минимальная важность: {level}\n\n"
            "Настройки относятся к служебным оповещениям, а не к рекламным рассылкам.")
    markup = {"inline_keyboard": [
        [{"text": "🔕 Отключить" if enabled else "🔔 Включить",
          "callback_data": "cp:settings:notifications:toggle"}],
        [{"text": "⚙️ Изменить важность", "callback_data": "cp:settings:notifications:level"}],
        [{"text": "⬅️ Настройки", "callback_data": "settings:menu"}],
    ]}
    return text, markup
