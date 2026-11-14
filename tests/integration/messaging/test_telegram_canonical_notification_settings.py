"""P1: Telegram notification settings use the existing event-store subscription owner."""
from __future__ import annotations

from types import SimpleNamespace

from core.policies.telegram.routes.settings_routes import handle_settings_routes
from interfaces.web.settings.common.eventstore_settings_gateway import EventStoreSettingsGateway
from runtime.handler_impl.domains.notification_settings_ops import notification_preferences
from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY
from runtime.settings.event_store_gateway import build_event_store_settings_gateway


class Store:
    def __init__(self):
        self.values = {}

    def get_setting(self, *, tenant_id, key):
        return self.values.get((tenant_id, key))

    def set_setting(self, *, tenant_id, key, value):
        self.values[(tenant_id, key)] = value

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        loc = (tenant_id, key)
        if self.values.get(loc) != expected:
            return False
        self.values[loc] = value
        return True


def test_toggle_persists_and_reopens_without_touching_other_user():
    store = Store()
    gateway = build_event_store_settings_gateway(event_store=store)
    assert isinstance(gateway, EventStoreSettingsGateway)
    before = [{"recipient_user_id": "other", "channel": "telegram",
               "min_level": "critical", "business_id": "", "enabled": True}]
    gateway.set_value(tenant_id="t1", key=SETTING_KEY, value=before)
    text, kb = notification_preferences(settings_gateway=gateway, tenant_id="t1", user_id="owner",
                                        operation="notifications_toggle")
    assert "включены" in text and kb["inline_keyboard"]
    value = gateway.get_value(tenant_id="t1", key=SETTING_KEY)
    assert len(value) == 2 and value[0]["recipient_user_id"] == "other"
    assert gateway.get_value(tenant_id="t2", key=SETTING_KEY) is None
    assert "включены" in notification_preferences(settings_gateway=gateway, tenant_id="t1", user_id="owner",
                                                   operation="notifications_show")[0]
    assert "выключены" in notification_preferences(settings_gateway=gateway, tenant_id="t1", user_id="owner",
                                                     operation="notifications_toggle")[0]
    assert "info" in notification_preferences(settings_gateway=gateway, tenant_id="t1", user_id="owner",
                                              operation="notifications_level")[0]


def test_telegram_routes_use_one_canonical_action_and_deny_nonadmin():
    def ctx(callback, is_admin):
        return SimpleNamespace(callback_data=callback, is_admin=is_admin, callback_query_id="cb",
                               cmd=None, state=SimpleNamespace(session={}))
    pm = lambda **kwargs: SimpleNamespace(action="send_message@v1", payload=kwargs)
    for callback, op in (("cp:settings:notifications", "notifications_show"),
                         ("cp:settings:notifications:toggle", "notifications_toggle"),
                         ("cp:settings:notifications:level", "notifications_level")):
        denied = handle_settings_routes(ctx(callback, False), user_id="u", bot_username="", pm=pm)
        assert denied.action == "send_message@v1"
        allowed = handle_settings_routes(ctx(callback, True), user_id="u", bot_username="", pm=pm)
        assert allowed.action == "business_admin@v1"
        assert allowed.payload["op"] == op and allowed.payload["callback_query_id"] == "cb"
