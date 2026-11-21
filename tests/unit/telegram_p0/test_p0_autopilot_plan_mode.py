"""Autopilot must not claim external actions when only a session was saved."""
from __future__ import annotations

from types import SimpleNamespace

from governance.time_scale import TimeScale, assert_action_allowed


def _ctx(flags):
    return SimpleNamespace(
        state=SimpleNamespace(
            tenant_id="tenant-x", timestamp_ms=123, product={}),
        marketing_seed="1", callback_query_id="callback-7",
        meta={}, settings={}, autopilot_dashboard={},
        )


def test_runtime_allows_plan_only_autopilot_action():
    assert_action_allowed("ads_autopilot_tick@v1", TimeScale.RUNTIME)


def test_operator_flag_is_false_by_default():
    from core.policies.telegram.context import operator_flag

    assert operator_flag(_ctx({}), "autopilot_execute") is False
    assert operator_flag(SimpleNamespace(state=SimpleNamespace(
        meta={"operator_flags": {"autopilot_execute": True}})), "autopilot_execute") is True


def test_planner_is_non_spending():
    from runtime.handlers.ads_autopilot.request_builder import build_autopilot_request

    req = build_autopilot_request(
        payload={"tenant_id": "tenant-x", "max_daily_budget_minor": 100000},
        route=SimpleNamespace(decision_id="d", correlation_id="c"),
    )
    assert req.dry_run is True
    assert req.plan_only is True
    assert req.apply_enabled is False
