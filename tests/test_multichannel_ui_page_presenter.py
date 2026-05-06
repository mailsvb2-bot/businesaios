from interfaces.web.settings.messaging_preferences.page_presenter import present_page


def test_present_page_marks_primary_enabled_and_verified():
    model = present_page(
        {
            "primary": "email",
            "enabled": ["telegram", "email"],
            "verified": ["email"],
        }
    )
    assert model.primary == "email"
    assert "email" in model.enabled
    assert "email" in model.verified
    assert len(model.groups) == 3
