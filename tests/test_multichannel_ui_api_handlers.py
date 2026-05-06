from interfaces.web.settings.messaging_preferences.api_handlers import MessagingPreferencesAPIHandlers


def test_api_handlers_return_page_model():
    api = MessagingPreferencesAPIHandlers()
    out = api.get_page_model({"primary": "telegram", "enabled": ["telegram"]})
    assert out["setting_key"] == "messaging:channel_preference"
    assert out["primary"] == "telegram"
    assert isinstance(out["groups"], list)
    assert len(out["groups"]) == 3


def test_api_handlers_save_preferences():
    api = MessagingPreferencesAPIHandlers()
    out = api.save_preferences(
        {
            "primary": "whatsapp",
            "enabled": ["telegram", "whatsapp"],
            "verified": ["whatsapp"],
        }
    )
    assert out["setting_key"] == "messaging:channel_preference"
    assert out["saved_value"]["primary"] == "whatsapp"
    assert out["saved_value"]["enabled"] == ["whatsapp", "telegram"]
