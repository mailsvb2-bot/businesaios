from interfaces.web.settings.alert_subscriptions.page_presenter import present_page


def test_present_page_builds_model():
    model = present_page(
        [
            {
                "recipient_user_id": "ceo-1",
                "channel": "slack",
                "min_level": "warn",
                "business_id": "business-a",
                "enabled": True,
                "code_filters": ["low_success_rate"],
                "user_scope": ["user-42"],
            }
        ],
        tenant_id="t1",
    )
    assert model.setting_key == "messaging_policy:alert_subscriptions"
    assert len(model.items) == 1
    assert model.items[0].business_id == "business-a"
    assert {item.key for item in model.channels} >= {"slack", "discord"}
    assert len(model.levels) == 3
