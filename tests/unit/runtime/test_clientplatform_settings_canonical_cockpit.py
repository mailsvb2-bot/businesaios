"""Settings callbacks must use the canonical owner cockpit rather than stub messages."""
from __future__ import annotations

from types import SimpleNamespace

from core.policies.telegram.routes.settings_routes import handle_settings_routes


def _ctx(callback: str, *, admin: bool):
    return SimpleNamespace(callback_data=callback, is_admin=admin, callback_query_id="cbq-1", cmd="",
                           state=SimpleNamespace(session={"selected_business_id": "business-123"}))


def test_clientplatform_settings_use_existing_canonical_actions():
    expected = {
        "cp:settings:organization": ("business_admin@v1", "organization_show", ""),
        "cp:settings:notifications": ("business_admin@v1", "notifications_show", ""),
        "cp:settings:access": ("business_ops_summary@v1", "cockpit", "cpm:team:0"),
    }
    for callback, (action, operation, arg) in expected.items():
        result = handle_settings_routes(
            _ctx(callback, admin=True),
            user_id="123",
            bot_username="clientplatform",
            pm=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must route through canonical action")),
        )
        assert result is not None
        assert result.action == action
        assert result.payload["op"] == operation
        assert result.payload["arg"] == arg
        assert result.payload["callback_query_id"] == "cbq-1"
        if callback == "cp:settings:organization":
            assert result.payload["business_id"] == "business-123"


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
        assert "администратору" in messages[0]["text"]


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
