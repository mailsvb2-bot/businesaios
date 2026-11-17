"""A visible connect action must lead to a safe public web onboarding handoff."""
from __future__ import annotations

from core.ux.unified_messenger_menu import (
    connect_business_view,
    telegram_menu,
    validated_onboarding_url,
)


def test_connect_navigation_is_a_callback() -> None:
    menu = telegram_menu(role="owner", is_admin=True)
    assert menu["inline_keyboard"][0][0]["callback_data"] == "cp:section:connect"


def test_link_validation_rejects_credential_and_query_injection() -> None:
    for bad in ("http://example.org", "https://user:secret@example.org",
                "https://example.org/?token=123", "https://example.org/#secret",
                "https://example.org\\n.evil", "https://example.org:8080/"):
        assert validated_onboarding_url(bad) == "https://app.businessaios.ru/"
    assert validated_onboarding_url("https://example.org/start") == "https://example.org/start"


def test_handoff_does_not_disclose_internal_binding_to_user() -> None:
    text, markup = connect_business_view(
        onboarding_url="https://example.org/start", bound_business_id="secret-business",
        show_binding=False,
    )
    assert "secret-business" not in text
    assert markup["inline_keyboard"][0][0]["url"] == "https://example.org/start"
    assert "telegram" not in markup["inline_keyboard"][0][0]["url"].lower()
    admin_text, _ = connect_business_view(
        onboarding_url="https://example.org/start", bound_business_id="secret-business",
        show_binding=True,
    )
    assert "secret-business" in admin_text
