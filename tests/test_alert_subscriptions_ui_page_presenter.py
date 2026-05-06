from interfaces.web.settings.alert_subscriptions.page_presenter import present_page


def test_present_page_builds_model():
    model = present_page(
        [
            {
                "recipient_user_id": "ceo-1",
                "channel": "telegram",
                "min_level": "warn",
                "enabled": True,
                "code_filters": ["low_success_rate"],
                "user_scope": ["user-42"],
            }
        ],
        tenant_id="t1",
    )
    assert model.setting_key == "messaging_policy:alert_subscriptions"
    assert len(model.items) == 1
    assert len(model.channels) >= 1
    assert len(model.levels) == 3
