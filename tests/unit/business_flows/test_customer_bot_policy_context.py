"""Customer bots: per-business policy context in DecisionCore, customer routes only."""

from __future__ import annotations

from dataclasses import replace

import pytest

from application.business_flows import bot_gateway as gw
from application.business_flows import catalog as cg
from core.policies.telegram.routes import customer_bot_routes as cbr
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS
from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from runtime.entrypoints.telegram_longpoll import _world_state_from_update

CAT = cg.replay([
    {"step": "profile_saved", "activity": "Студия йоги у метро", "timezone": "Europe/Moscow"},
    {"step": "offering_created", "offering_id": "o1", "format": "group", "title": "Утренняя йога", "description": "", "direction_id": None},
    {"step": "offering_created", "offering_id": "o2", "format": "group", "title": "Архив", "description": "", "direction_id": None},
    {"step": "offering_archived", "offering_id": "o2"},
])  # fmt: skip
ROUTE = gw.with_business([gw.Route("biz-7", "r1", "777", "yoga_bot", "vault:managed_bot.biz-7.r1", "5001")],
                         gw.business_context(CAT))[0]  # fmt: skip


def _state(text, user=42, monkeypatch=None):
    upd = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": user}, "from": {"id": user, "first_name": "A"}, "text": text}}
    return _world_state_from_update(upd, transport="customer_bot", customer_route=ROUTE)


@pytest.fixture(autouse=True)
def _main_tenant(monkeypatch):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "main")


def test_source_literal_matches_application():
    assert cbr.CUSTOMER_SOURCE == gw.SESSION_SOURCE


def test_business_context_public_and_live_only():
    ctx = dict(gw.business_context(CAT))
    assert ctx["activity"] == "Студия йоги у метро" and ctx["offerings"] == ("Утренняя йога",)
    assert "vault" not in repr(ctx)


def test_world_state_uses_route_tenant_and_business():
    st = _state("/start")
    assert st.tenant_id == "biz-7"
    bot = st.session["customer_bot"]
    assert bot["tenant_id"] == "biz-7" and bot["business"]["activity"] == "Студия йоги у метро"
    assert "credential_ref" not in bot and "vault:" not in repr(st.session)


def test_start_greets_with_business_menu():
    out = UnifiedTelegramPolicyV3().propose(_state("/start"))
    text = out.payload["text"]
    assert "@yoga_bot" in text and "Студия йоги" in text and "Утренняя йога" in text and "/slots" in text


@pytest.mark.parametrize("cmd", cbr.CUSTOMER_COMMANDS)
def test_customer_commands_route_through_same_table(cmd):
    out = UnifiedTelegramPolicyV3().propose(_state(cmd + " x"))
    action, op, _ = BUSINESS_FLOW_COMMANDS[cmd]
    assert out.action == action and out.payload["op"] == op


@pytest.mark.parametrize("cmd", [c for c, (_a, _o, owner) in BUSINESS_FLOW_COMMANDS.items() if owner])
def test_owner_commands_refused_even_for_superadmin(cmd):
    policy = UnifiedTelegramPolicyV3(admin_user_ids=("42",))
    out = policy.propose(_state(cmd, user=42))
    assert out.payload.get("op") is None and "основном боте" in out.payload["text"]


def test_superadmin_gets_no_admin_ui_or_cockpit_on_customer_bot():
    policy = UnifiedTelegramPolicyV3(admin_user_ids=("42",))
    out = policy.propose(_state("/me", user=42))
    assert out.payload["op"] == "home"  # not home_owner
    assert all(a.payload.get("op") != "cockpit" for a in policy.propose_many(_state("/admin", user=42)))


def test_main_bot_unchanged():
    st = _world_state_from_update(
        {"update_id": 2, "message": {"message_id": 2, "chat": {"id": 5}, "from": {"id": 5}, "text": "/slots"}}
    )
    assert st.tenant_id == "main" and st.session.get("source") != cbr.CUSTOMER_SOURCE
    assert replace(ROUTE).business == ROUTE.business
