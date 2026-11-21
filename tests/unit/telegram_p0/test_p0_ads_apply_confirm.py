"""Ads Apply confirms one verified pending plan through canonical executor."""
from __future__ import annotations

from types import SimpleNamespace

from core.policies.telegram.handlers.ads_apply_flow import propose_confirmed_apply
from governance.time_scale import TimeScale, assert_action_allowed


def _ctx(*, live=False, enabled=True):
    return SimpleNamespace(
        settings={"ads:apply_enabled": {"enabled": enabled, "since_ms": 100}},
        callback_query_id="cb-1",
        state=SimpleNamespace(meta={"operator_flags": {"ads_apply_live": live}}),
    )


def _pending():
    return {"platform": "vk", "daily_budget_minor": 1000,
            "ops": [{"action": "update_budget", "payload": {"campaign_id": "c1"}}]}


def test_default_confirm_is_dry_run_and_idempotent():
    ctx = _ctx()
    a = propose_confirmed_apply(ctx, user_id="u1", pending=_pending())
    b = propose_confirmed_apply(ctx, user_id="u1", pending=_pending())
    assert a is not None
    assert a.action == b.action
    assert a.payload["dry_run"] is True
    assert a.payload["idempotency_key"] == b.payload["idempotency_key"]
    assert a.payload["plan"][0]["payload"]["daily_budget_minor"] == 1000


def test_live_switch_requires_operator_setting_and_confirmed_plan():
    enabled = propose_confirmed_apply(_ctx(live=True), user_id="u1", pending=_pending())
    assert enabled.payload["dry_run"] is False
    assert enabled.payload["gate_settings"]["ads:apply_enabled"] is True
    assert propose_confirmed_apply(_ctx(live=True), user_id="u1", pending={}) is None


def test_ads_apply_runtime_registration_exists():
    assert_action_allowed("ads_apply_execute@v1", TimeScale.RUNTIME)
