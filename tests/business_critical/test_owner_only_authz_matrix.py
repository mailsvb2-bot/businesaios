"""Owner-only commands never reach a non-admin: router level and admin-command handler level."""

from __future__ import annotations

import pytest

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.commands import ADMIN_COMMANDS, handle_admin_commands
from core.policies.telegram.helpers import normalize_proposed_action
from core.policies.telegram.router import handle
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS, handle_business_flow_routes

OWNER_ONLY = sorted(c for c, (_a, _o, owner_only) in BUSINESS_FLOW_COMMANDS.items() if owner_only)
CUSTOMER_OK = sorted(c for c, (_a, _o, owner_only) in BUSINESS_FLOW_COMMANDS.items() if not owner_only)


class _State:
    user_id = "u1"
    tenant_id = "t1"
    product = {"product_id": "organization_platform", "domain": "organization_platform"}
    economy: dict = {}


def _ctx(cmd: str, *, is_admin: bool, full_access: bool = False, metrics: dict | None = None) -> TelegramCtx:
    return TelegramCtx(
        state=_State(), text=cmd, cmd=cmd, args="", callback_data="", callback_query_id=None, settings={},
        city="", moods=[], admin_metrics=metrics if metrics is not None else {}, is_admin=is_admin, roles=[], perms=[],
        is_superadmin=False, realtime_state={}, pricing_suggestions={}, full_access=full_access, pay_status="none",
        selected_tariff={}, marketing_variants={}, marketing_seed="1", marketing_bandit={},
    )


def _owner_actions() -> dict[str, tuple[str, str]]:
    return {c: (BUSINESS_FLOW_COMMANDS[c][0], BUSINESS_FLOW_COMMANDS[c][1]) for c in OWNER_ONLY}


def test_owner_only_set_is_large_and_includes_the_sensitive_commands() -> None:
    assert len(OWNER_ONLY) > 100  # a shrinking set must be a conscious change
    assert {"/connect_bot", "/cancel_bot", "/add_slot"} <= set(OWNER_ONLY)
    assert CUSTOMER_OK and not set(CUSTOMER_OK) & set(OWNER_ONLY)


@pytest.mark.parametrize("full_access", [False, True])
def test_business_flow_route_gives_non_admin_no_owner_only_action(full_access) -> None:
    leaked = [c for c in OWNER_ONLY if handle_business_flow_routes(_ctx(c, is_admin=False, full_access=full_access), user_id="u1") is not None]
    assert leaked == []


def test_business_flow_route_gives_admin_every_owner_only_action() -> None:
    """Without this the matrix above passes trivially if the route table stops matching at all."""
    expected = _owner_actions()
    for cmd in OWNER_ONLY:
        act = normalize_proposed_action(handle_business_flow_routes(_ctx(cmd, is_admin=True), user_id="u1"))
        assert (act.action, act.payload["op"]) == expected[cmd] or cmd in {"/me", "/customers"}, cmd


@pytest.mark.parametrize("full_access", [False, True])
def test_full_router_gives_non_admin_no_owner_only_action(full_access) -> None:
    expected = _owner_actions()
    leaked = []
    for cmd in OWNER_ONLY:
        act = handle(_ctx(cmd, is_admin=False, full_access=full_access), default_price_rub=4900)
        if act is None:
            continue
        act = normalize_proposed_action(act)
        if (act.action, act.payload.get("op")) == expected[cmd]:
            leaked.append(cmd)
    assert leaked == []


def test_customer_commands_stay_available_to_non_admin() -> None:
    for cmd in CUSTOMER_OK:
        act = handle_business_flow_routes(_ctx(cmd, is_admin=False), user_id="u1")
        assert act is not None, cmd
        assert normalize_proposed_action(act).action == BUSINESS_FLOW_COMMANDS[cmd][0]


def _pm(*, text, reply_markup=None):
    return {"text": text, "reply_markup": reply_markup}


_METRICS = {"demo_summary": {"users": 4242, "sent_work": 7, "sent_home": 8}, "funnel": {"tariffs_viewed": 4242}}


def test_admin_command_handler_refuses_non_admin_for_every_admin_command() -> None:
    denied = {c: handle_admin_commands(_ctx(c, is_admin=False, metrics=_METRICS), pm=_pm) for c in sorted(ADMIN_COMMANDS)}
    assert set(denied) == ADMIN_COMMANDS and all(v is not None for v in denied.values())
    assert len({v["text"] for v in denied.values()}) == 1  # one identical refusal, not a per-command answer
    refusal = next(iter(denied.values()))["text"]
    assert "4242" not in refusal and "/demo_stats" not in refusal


def test_admin_command_handler_serves_admin_differently_from_non_admin() -> None:
    refusal = handle_admin_commands(_ctx("/admin", is_admin=False), pm=_pm)["text"]
    for cmd in ("/admin", "/demo_stats", "/funnel"):
        served = handle_admin_commands(_ctx(cmd, is_admin=True, metrics=_METRICS), pm=_pm)["text"]
        assert served != refusal, cmd
    assert "4242" in handle_admin_commands(_ctx("/demo_stats", is_admin=True, metrics=_METRICS), pm=_pm)["text"]


def test_admin_command_handler_ignores_other_commands() -> None:
    assert handle_admin_commands(_ctx("/start", is_admin=False), pm=_pm) is None
