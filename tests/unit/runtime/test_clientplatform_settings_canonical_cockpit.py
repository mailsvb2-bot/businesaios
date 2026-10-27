"""Settings callbacks must use the canonical owner cockpit rather than stub messages."""
from __future__ import annotations

from types import SimpleNamespace

from core.policies.telegram.routes.settings_routes import handle_settings_routes


def _ctx(callback: str, *, admin: bool):
    return SimpleNamespace(callback_data=callback, is_admin=admin, callback_query_id="cbq-1", cmd="")


def test_clientplatform_settings_use_existing_cockpit_action():
    expected = {
        "cp:settings:organization": "cpm:manage",
        "cp:settings:notifications": "cpm:automation",
        "cp:settings:access": "cpm:team:0",
    }
    for callback, screen in expected.items():
        result = handle_settings_routes(
            _ctx(callback, admin=True),
            user_id="123",
            bot_username="clientplatform",
            pm=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must route through canonical action")),
        )
        assert result is not None
        assert result.action == "business_ops_summary@v1"
        assert result.payload["op"] == "cockpit"
        assert result.payload["arg"] == screen
        assert result.payload["callback_query_id"] == "cbq-1"


def test_clientplatform_settings_deny_non_admin():
    for callback in ("cp:settings:organization", "cp:settings:notifications", "cp:settings:access"):
        messages = []
        result = handle_settings_routes(
            _ctx(callback, admin=False),
            user_id="999",
            bot_username="clientplatform",
            pm=lambda **kw: messages.append(kw) or object(),
        )
        assert result is not None
        assert len(messages) == 1
        assert "только администратору" in messages[0]["text"]


def test_settings_menu_uses_real_newlines():
    from core.ux.callbacks import CB_SETTINGS_MENU

    messages = []
    handle_settings_routes(
        _ctx(CB_SETTINGS_MENU, admin=True),
        user_id="123",
        bot_username="clientplatform",
        pm=lambda **kw: messages.append(kw) or object(),
    )
    assert "\n\n" in messages[0]["text"]
    assert r"\n" not in messages[0]["text"]
