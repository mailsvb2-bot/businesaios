from interfaces.web.settings.messaging_preferences.form_parser import parse_preference_form


def test_parse_preference_form_normalizes_and_keeps_primary():
    out = parse_preference_form(
        {
            "primary": "WhatsApp",
            "enabled": ["telegram", "whatsapp", "telegram"],
            "verified": ["whatsapp"],
        }
    )
    assert out["primary"] == "whatsapp"
    assert out["enabled"] == ["whatsapp", "telegram"]
    assert out["verified"] == ["whatsapp"]
