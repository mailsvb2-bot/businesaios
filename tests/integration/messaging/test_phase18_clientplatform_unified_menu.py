from __future__ import annotations

import pytest

from core.ux.callbacks import (
    CB_ADMIN_MENU, CB_AUTOPILOT_MENU, CB_GROWTH_MENU, CB_MENU_MAIN,
    CB_SETTINGS_MENU, CB_SETTINGS_STATE, CB_SUB_MENU,
)
from core.ux.unified_messenger_menu import (
    BRAND, menu_items, menu_text, telegram_menu, plain_channel_menu,
    section_text, back_button,
)
from core.ux.keyboards.main import kb_main


def test_brand_and_owner_navigation_are_stable():
    assert BRAND == "ClientPlatform"
    keys = [x.key for x in menu_items(role="owner", is_admin=True)]
    assert keys == ["customers", "sales", "marketing", "ai",
                    "results", "payments", "settings", "administration"]
    assert "ClientPlatform" in menu_text(role="owner", is_admin=True)
    callbacks = [row[0]["callback_data"] for row in telegram_menu(role="owner", is_admin=True)["inline_keyboard"]]
    assert callbacks[2:] == [
        CB_GROWTH_MENU, CB_AUTOPILOT_MENU, CB_SETTINGS_STATE,
        CB_SUB_MENU, CB_SETTINGS_MENU, CB_ADMIN_MENU,
    ]
    assert kb_main() == telegram_menu(role="owner")


def test_role_visibility_cannot_expose_admin_or_payments_to_operator():
    operator = menu_items(role="operator")
    assert "administration" not in [x.key for x in operator]
    assert "payments" not in [x.key for x in operator]
    assert "settings" not in [x.key for x in operator]
    assert "customers" not in [x.key for x in operator]
    assert "sales" not in [x.key for x in operator]
    admin = menu_items(role="owner", is_admin=True)
    assert admin[-1].callback == CB_ADMIN_MENU


@pytest.mark.parametrize("channel", [
    "telegram", "vk", "max", "whatsapp", "viber", "instagram",
    "messenger", "line", "slack", "discord", "wechat", "kakaotalk",
])
def test_channels_share_exact_same_navigation_semantics(channel):
    result = plain_channel_menu(channel=channel, role="owner", is_admin=True)
    assert result["channel"] == channel
    assert result["text"] == menu_text(role="owner", is_admin=True)
    assert tuple(row["callback"] for row in result["actions"]) == tuple(
        row[0]["callback_data"] for row in telegram_menu(role="owner")["inline_keyboard"]
    )


def test_unsupported_provider_fails_closed_without_fake_button_support():
    with pytest.raises(ValueError):
        plain_channel_menu(channel="fictional_messenger", role="owner")


def test_placeholder_sections_never_pretend_live_crm_route_is_connected():
    assert section_text("cp:section:customers") is None
    assert section_text("cp:section:sales") is None
    assert section_text("ads:apply:confirm") is None
    assert back_button()["inline_keyboard"][0][0]["callback_data"] == CB_MENU_MAIN


def test_every_registered_messaging_channel_has_text_navigation():
    from application.business_autonomy.provider_catalog import MESSAGING_CHANNEL_PROVIDER_KEYS

    for channel in MESSAGING_CHANNEL_PROVIDER_KEYS:
        page = plain_channel_menu(channel=channel, role="owner")
        assert page["text"].startswith("🏠 ClientPlatform")
        assert page["actions"]


def test_canonical_user_role_from_settings_controls_unified_keyboard():
    from core.users.roles import UserRoleInfo

    marketer = UserRoleInfo.from_settings({"user:role": "marketer"})
    owner = UserRoleInfo.from_settings({"user:role": "owner"})
    assert "🧩 Ads Apply (prod)" in [
        button["text"] for row in kb_main(role=marketer)["inline_keyboard"] for button in row
    ]
    assert "🧩 Ads Apply (prod)" not in [
        button["text"] for row in kb_main(role=owner)["inline_keyboard"] for button in row
    ]
