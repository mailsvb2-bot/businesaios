from __future__ import annotations

import pytest

from core.ux.callbacks import (
    CB_ADMIN_MENU, CB_AUTOPILOT_MENU, CB_GROWTH_MENU, CB_MENU_MAIN,
    CB_SETTINGS_MENU, CB_SETTINGS_STATE, CB_SUB_MENU,
)
from core.ux.clientplatform_unified_menu import (
    BRAND, menu_items, menu_text, telegram_menu, plain_channel_menu,
    section_text, back_button,
)
from core.ux.keyboards.main import kb_main


def test_brand_and_owner_navigation_are_stable():
    assert BRAND == "ClientPlatform"
    keys = [x.key for x in menu_items(role="owner")]
    assert keys == ["customers", "sales", "marketing", "ai",
                    "results", "payments", "settings"]
    assert "ClientPlatform" in menu_text(role="owner")
    callbacks = [row[0]["callback_data"] for row in telegram_menu(role="owner")["inline_keyboard"]]
    assert callbacks[2:] == [
        CB_GROWTH_MENU, CB_AUTOPILOT_MENU, CB_SETTINGS_STATE,
        CB_SUB_MENU, CB_SETTINGS_MENU,
    ]
    assert kb_main() == telegram_menu(role="owner")


def test_role_visibility_cannot_expose_admin_or_payments_to_operator():
    operator = menu_items(role="operator")
    assert "administration" not in [x.key for x in operator]
    assert "payments" not in [x.key for x in operator]
    assert "settings" not in [x.key for x in operator]
    assert "customers" in [x.key for x in operator]
    admin = menu_items(role="owner", is_admin=True)
    assert admin[-1].callback == CB_ADMIN_MENU


@pytest.mark.parametrize("channel", ["telegram", "vk", "max"])
def test_channels_share_exact_same_navigation_semantics(channel):
    result = plain_channel_menu(channel=channel, role="owner")
    assert result["channel"] == channel
    assert result["text"] == menu_text(role="owner")
    assert tuple(row["callback"] for row in result["actions"]) == tuple(
        row[0]["callback_data"] for row in telegram_menu(role="owner")["inline_keyboard"]
    )


def test_unsupported_provider_fails_closed_without_fake_button_support():
    with pytest.raises(ValueError):
        plain_channel_menu(channel="whatsapp", role="owner")


def test_placeholder_sections_never_pretend_live_crm_route_is_connected():
    assert "рабочем пространстве" in section_text("cp:section:customers")
    assert "рабочем пространстве" in section_text("cp:section:sales")
    assert section_text("ads:apply:confirm") is None
    assert back_button()["inline_keyboard"][0][0]["callback_data"] == CB_MENU_MAIN
