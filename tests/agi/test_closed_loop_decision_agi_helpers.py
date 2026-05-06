from __future__ import annotations

from execution.closed_loop_orchestrator import _compact_decision_agi_payload, _extract_decision_agi_payload
from kernel.world_state import WorldStateV1


def test_extract_decision_agi_payload_prefers_full_payload():
    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=1,
        meta={
            "decision_agi": {
                "selected_goal": {"goal": "restore demand generation", "goal_family": "pipeline_growth"},
                "planning_horizon": "week",
                "strategy_hints": [{"hint_key": "prefer_verified_growth"}],
            }
        },
    )
    payload = _extract_decision_agi_payload(state)
    assert payload["selected_goal"]["goal"] == "restore demand generation"


def test_compact_decision_agi_payload_is_stable_and_small():
    compact = _compact_decision_agi_payload(
        {
            "selected_goal": {"goal": "restore demand generation", "goal_family": "pipeline_growth", "priority": "high", "source": "opportunity_detector"},
            "planning_horizon": "week",
            "strategy_hints": [
                {"hint_key": "prefer_verified_growth", "confidence": 0.7, "reason": "growth_family"},
                {"hint_key": "prefer_verified_growth", "confidence": 0.7, "reason": "growth_family"},
            ],
            "opportunity_signals": [{"signal_type": "demand_gap"}, {"signal_type": "goal_gap"}],
            "suppressed_reasons": ["goal_candidates_capped"],
        }
    )
    assert compact["selected_goal"] == "restore demand generation"
    assert compact["selected_goal_family"] == "pipeline_growth"
    assert compact["planning_horizon"] == "week"
    assert compact["signal_count"] == 2
    assert compact["no_second_brain"] is True


def test_compact_decision_agi_payload_adds_and_decrements_planning_ttl():
    compact = _compact_decision_agi_payload(
        {
            "selected_goal": {"goal": "restore demand generation", "goal_family": "pipeline_growth"},
            "planning_horizon": "week",
        }
    )
    assert compact["planning_ttl"] == 7

    compact2 = _compact_decision_agi_payload(
        {
            "selected_goal": {"goal": "restore demand generation", "goal_family": "pipeline_growth"},
            "planning_horizon": "week",
            "planning_ttl": 7,
        }
    )
    assert compact2["planning_ttl"] == 6
