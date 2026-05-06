from interfaces.web.settings.alert_subscriptions.api_handlers import AlertSubscriptionsAPIHandlers


def test_api_handlers_return_page_model():
    api = AlertSubscriptionsAPIHandlers()
    out = api.get_page_model([], tenant_id="t1")
    assert out["setting_key"] == "messaging_policy:alert_subscriptions"
    assert isinstance(out["items"], list)
    assert isinstance(out["channels"], list)
    assert isinstance(out["levels"], list)


def test_api_handlers_save_subscriptions():
    api = AlertSubscriptionsAPIHandlers()
    out = api.save_subscriptions(
        {
            "items": [
                {
                    "recipient_user_id": "ceo-1",
                    "channel": "telegram",
                    "min_level": "warn",
                    "enabled": True,
                    "code_filters": [],
                    "user_scope": [],
                }
            ]
        }
    )
    assert out["setting_key"] == "messaging_policy:alert_subscriptions"
    assert out["saved_value"][0]["recipient_user_id"] == "ceo-1"
