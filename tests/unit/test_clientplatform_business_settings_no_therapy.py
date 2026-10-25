"""Regression: Business bot cannot leak therapy settings through old callbacks."""
from types import SimpleNamespace

from core.policies.telegram.routes.settings_routes import handle_settings_routes
from core.ux.callbacks import CB_SETTINGS_MENU, CB_SETTINGS_STATE
from core.ux.keyboards.settings import kb_settings_menu


def _route(callback: str = "", cmd: str | None = None):
    ctx = SimpleNamespace(callback_data=callback, cmd=cmd)
    return handle_settings_routes(ctx, user_id="u", bot_username="clientplatform_bot",
                                  pm=lambda **kw: kw)


def test_business_settings_only_contain_business_sections():
    result = _route(CB_SETTINGS_MENU)
    assert "ClientPlatform" in result["text"]
    assert "погод" not in result["text"]
    keyboard = kb_settings_menu()["inline_keyboard"]
    callbacks = [b["callback_data"] for row in keyboard for b in row]
    assert "cp:settings:organization" in callbacks
    assert "cp:settings:access" in callbacks
    assert not any(c.startswith(("settings:time:", "settings:ref", "state:")) for c in callbacks)


def test_stale_therapy_callbacks_fail_closed():
    for callback in ("settings:time:work", "settings:time:home", "settings:ref",
                     "state:rate", "state:rate:10", "state:today", "state:yesterday",
                     "state:all", CB_SETTINGS_STATE, "settings:state"):
        result = _route(callback)
        assert result is not None, callback
        assert "не относится" in result["text"], callback
    for command in ("/time_work", "/time_home"):
        assert "не относится" in _route(cmd=command)["text"]


def test_business_settings_pages_render_without_therapy_content():
    for callback in ("cp:settings:organization", "cp:settings:notifications", "cp:settings:access"):
        result = _route(callback)
        assert result is not None
        assert "Утро" not in result["text"]
        assert "Состояния" not in result["text"]
