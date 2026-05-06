from __future__ import annotations

from execution.agi_reasoning_engine import AGIReasoningEngine
from kernel.world_state import WorldStateV1


def test_decision_agi_summary_has_stable_enterprise_shape():
    engine = AGIReasoningEngine()
    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={"user_id": "u1"},
        session={"inbound_leads": 0, "outbound_count": 0},
        product={"product_id": "p1"},
        economy={},
        timestamp_ms=1710000000000,
        user_id="u1",
        meta={
            "business_memory_evidence": {"active_goals": ["increase revenue safely"]},
            "runtime_capabilities": {"analytics_read": {"status": "ok"}},
        },
    )
    summary = engine.build_summary(state=state, world_snapshot={}).to_dict()
    assert summary["schema_version"] == "agi_reasoning@v3"
    assert summary["reasoning_mode"] == "state_enrichment_only"
    assert isinstance(summary["goal_candidates"], list)
    assert isinstance(summary["strategy_hints"], list)
    assert isinstance(summary["opportunity_signals"], list)
    assert isinstance(summary["learning_context"], dict)
    assert isinstance(summary["explainability"], dict)
    assert isinstance(summary["suppressed_reasons"], list)
