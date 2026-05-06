from __future__ import annotations

from application.decision_runtime.runtime import build_trace
from kernel.world_state import WorldStateV1


def _step_names(trace) -> list[str]:
    items = list(getattr(trace, "steps", None) or getattr(trace, "_steps", ()) or ())
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            out.append(str(item.get("name") or ""))
        else:
            out.append(str(getattr(item, "name", "") or ""))
    return out


def test_build_trace_keeps_canonical_world_model_steps_and_adds_decision_agi_summary():
    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={"user_id": "u1"},
        session={},
        product={},
        economy={"pricing_world_state": {"expected_profit": 12.0, "expected_revenue": 49.0}},
        timestamp_ms=1710000000000,
        user_id="u1",
        meta={
            "world_model": "decision_agi_world_model@v1",
            "world_model_kind": "decision_agi@v1",
            "decision_agi_summary": {
                "selected_goal": "restore demand generation",
                "selected_goal_family": "pipeline_growth",
                "planning_horizon": "week",
                "signal_count": 2,
                "strategy_hints": [{"hint_key": "prefer_verified_growth", "confidence": 0.7, "reason": "growth_family"}],
                "reasoning_mode": "state_enrichment_only",
            },
        },
    )
    _, trace, world_model_meta = build_trace(state=state, issuer_id="businesaios-core", envelope_version=1)
    names = _step_names(trace)
    assert "world_model_metadata" in names
    assert "pricing_world_state_summary" in names
    assert "decision_agi_summary" in names
    assert world_model_meta["world_model"] == "decision_agi_world_model@v1"
