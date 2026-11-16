"""Executable inventory for ClientPlatform's visible Telegram/VK/MAX buttons.

A routed callback is not sufficient: it must pass the canonical action schema,
preserve callback acknowledgement, and never fall through to a missing screen.
"""
from dataclasses import replace

import pytest

from application.business_flows.cockpit import Snapshot, parse, render
from application.decision_runtime.flow import build_payload
from core.actions.catalog import build_schema_registry
from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.ux.keyboards import admin, autopilot, payments, settings
from core.ux.telegram_keyboards_ai_ceo import kb_ai_ceo_menu
from core.ux.unified_messenger_menu import (
    BUSINESS_ONBOARDING_URL,
    plain_channel_menu,
    telegram_menu,
)
from runtime.boot.actions_registry import handler_actions
from runtime.entrypoints.telegram_longpoll import _world_state_from_update


def _keyboards():
    return (
        telegram_menu(role="admin", is_admin=True),
        telegram_menu(role="owner", is_admin=False),
        telegram_menu(role="operator", is_admin=False),
        telegram_menu(role="marketer", is_admin=False),
        admin.kb_staff_menu(),
        autopilot.kb_autopilot_menu(),
        autopilot.kb_profit_sprint_lead_sources(),
        autopilot.kb_ads_apply_pending(),
        autopilot.kb_growth_menu(),
        kb_ai_ceo_menu(can_run=True),
        settings.kb_demo_kind(),
        settings.kb_weather(),
        settings.kb_state_menu(),
        settings.kb_mood_rate(),
        settings.kb_settings_menu(),
        payments.kb_gift_menu(),
        payments.kb_pay_selected(),
        payments.kb_tariffs([{"plan_id": 1, "title": "Test", "price": 100}]),
    )


def _callbacks():
    return sorted({
        button["callback_data"]
        for keyboard in _keyboards()
        for row in keyboard["inline_keyboard"]
        for button in row
        if "callback_data" in button
    })


def _owner_update(callback):
    return {
        "update_id": 123,
        "callback_query": {
            "id": "callback-123",
            "from": {"id": 4001},
            "message": {
                "message_id": 15,
                "date": 1700000000,
                "chat": {"id": 4001},
            },
            "data": callback,
        },
    }


@pytest.mark.parametrize("callback", _callbacks())
def test_every_static_button_passes_policy_and_closed_action_schema(monkeypatch, callback):
    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    assert len(callback.encode("utf-8")) <= 64, callback
    state = _world_state_from_update(_owner_update(callback))
    state = replace(state, user={**state.user, "roles": ["admin"]})
    proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    assert proposal.action in handler_actions(), callback
    assert "Этот раздел пока недоступен" not in str(proposal.payload.get("text") or "")
    _, payload = build_payload(
        state=state,
        out=proposal,
        pinned_world_model_meta={},
        tenant_id="tenant-live",
        product_id=None,
        domain=None,
        product_version=None,
        actor_id="4001",
    )
    build_schema_registry().validate(proposal.action, payload)
    if proposal.action == "send_message@v1":
        assert payload.get("callback_query_id") == "callback-123"


@pytest.mark.parametrize("channel", ["vk", "max"])
def test_cross_provider_connect_button_uses_existing_web_onboarding_owner(
    monkeypatch, channel,
):
    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    menu = plain_channel_menu(channel=channel, role="owner")
    button = next(item for item in menu["actions"] if item["key"] == "connect")
    assert button["callback"] == "cp:section:connect"
    state = replace(
        _world_state_from_update(_owner_update(button["callback"])),
        user={"id": "4001", "roles": []},
    )
    proposal = UnifiedTelegramPolicyV3().propose(state)
    assert proposal.action == "send_message@v1"
    assert BUSINESS_ONBOARDING_URL in proposal.payload["text"]
    assert proposal.payload["callback_query_id"] == "callback-123"
    buttons = [b for row in proposal.payload["reply_markup"]["inline_keyboard"] for b in row]
    assert any(b.get("url") == BUSINESS_ONBOARDING_URL for b in buttons)
    assert any(b.get("callback_data") == "menu:main" for b in buttons)
    assert "недоступен" not in proposal.payload["text"]
    assert "подключён" not in proposal.payload["text"]


def test_cockpit_menu_buttons_reach_renderable_canonical_screens():
    # Cover the actual nested owner cockpit navigation graph, not only top menu.
    seeds = ("cpm:menu", "cpm:growth", "cpm:money")
    checked, todo = set(), list(seeds)
    while todo and len(checked) < 150:
        callback = todo.pop(0)
        if callback in checked:
            continue
        checked.add(callback)
        assert len(callback.encode("utf-8")) <= 64
        body, rows = render(parse(callback), Snapshot(), is_owner=True)
        assert "Эта кнопка уже неактуальна" not in body, callback
        assert "Для Вашей роли этот раздел недоступен" not in body, callback
        for row in rows:
            for _label, dest in row:
                assert len(dest.encode("utf-8")) <= 64, dest
                if dest.startswith("cpm:") and dest not in checked:
                    todo.append(dest)
    assert len(checked) >= 30
