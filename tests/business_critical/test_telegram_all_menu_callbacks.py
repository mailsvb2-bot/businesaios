"""Executable Telegram menu contract: each visible button is a routed callback."""
from dataclasses import replace

import pytest

from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.ux.unified_messenger_menu import menu_items
from runtime.entrypoints.telegram_longpoll import _world_state_from_update


def _callback_state(callback):
    update = {
        "update_id": 12,
        "callback_query": {
            "id": "callback-12",
            "from": {"id": 4001},
            "message": {"message_id": 10, "date": 1700000000, "chat": {"id": 4001}},
            "data": callback,
        },
    }
    state = _world_state_from_update(update)
    return replace(state, user={**state.user, "roles": ["admin"]})


@pytest.mark.parametrize("item", menu_items(role="admin", is_admin=True), ids=lambda x: x.key)
def test_every_visible_main_menu_button_enters_its_own_route(monkeypatch, item):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = _callback_state(item.callback)
    policy = UnifiedTelegramPolicyV3()
    ctx, _ = policy._context(state)
    assert ctx.callback_data == item.callback
    assert ctx.callback_query_id == "callback-12"
    assert ctx.cmd is None or ctx.cmd == ""
    result = policy.propose(state)
    assert result.action, item.key
    if result.action == "send_message@v1":
        assert result.payload.get("text")
        assert "Я здесь. Напиши" not in result.payload["text"], item.key
        assert result.payload.get("callback_query_id") == "callback-12"


@pytest.mark.parametrize("callback", ["menu:main", "settings:state", "state:rate", "state:today", "settings:time:work", "settings:time:home"])
def test_nested_and_back_callbacks_never_fall_through(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3().propose(_callback_state(callback))
    assert result.action == "send_message@v1"
    assert "Я здесь. Напиши" not in result.payload["text"]


def _nested_buttons():
    from core.ux.keyboards.admin import kb_staff_menu
    from core.ux.keyboards.autopilot import kb_autopilot_menu, kb_growth_menu, kb_profit_sprint_lead_sources
    from core.ux.keyboards.settings import kb_settings_menu, kb_state_menu, kb_mood_rate
    keyboards = (kb_staff_menu(), kb_autopilot_menu(), kb_growth_menu(),
                 kb_profit_sprint_lead_sources(), kb_settings_menu(), kb_state_menu(), kb_mood_rate())
    return tuple(sorted({button["callback_data"] for keyboard in keyboards
                         for row in keyboard["inline_keyboard"] for button in row}))


@pytest.mark.parametrize("callback", _nested_buttons())
def test_all_nested_visible_buttons_have_concrete_route(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = _callback_state(callback)
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    assert result.action, callback
    if result.action == "send_message@v1":
        assert result.payload.get("text"), callback
        assert not result.payload["text"].startswith("Я здесь. Напиши"), callback


@pytest.mark.parametrize(("callback", "action", "operation"), [
    ("cp:section:customers", "business_ops_summary@v1", "cockpit"),
    ("cp:section:sales", "sales_pipeline@v1", "list"),
])
def test_owner_section_calls_existing_canonical_operation(monkeypatch, callback, action, operation):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(_callback_state(callback))
    assert result.action == action
    assert result.payload["op"] == operation
    assert result.payload["callback_query_id"] == "callback-12"


@pytest.mark.parametrize("callback", ["cp:section:customers", "cp:section:sales"])
def test_owner_section_rejects_unprivileged_telegram_user(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = replace(_callback_state(callback), user={"roles": ["operator"]})
    result = UnifiedTelegramPolicyV3().propose(state)
    assert result.action == "send_message@v1"
    assert "запрещён" in result.payload["text"]
