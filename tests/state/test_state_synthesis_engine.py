from __future__ import annotations

from runtime.market.market_snapshot import MarketSnapshot
from runtime.market.segment_trend_state import SegmentTrendState
from runtime.state import (
    StateSynthesisEngine,
    StateSynthesisRequest,
    apply_synthesized_world_view,
    build_world_state_observations,
)


def test_state_synthesis_engine_round_trip_world_view() -> None:
    market = MarketSnapshot(
        global_macro_score=0.6,
        global_micro_score=0.5,
        global_competitive_shift=0.4,
        segment_states=(
            SegmentTrendState(
                segment_key="core",
                macro_score=0.7,
                micro_score=0.5,
                persistence_score=0.8,
                competitive_shift_score=0.3,
            ),
        ),
    )
    engine = StateSynthesisEngine()
    snapshot = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant",
            business_id="business",
            now_ms=123,
            observations=build_world_state_observations(
                generated_at_ms=123,
                user_observables={"intent_index": 0.8},
                market_snapshot=market,
                architecture_state={"global_stability": 0.9},
                structure_state={"blast_radius_risk": 0.1},
                flow_state={"velocity": 0.4},
                diffusion_state={"spread_index": 0.2},
            ),
        )
    )

    user_observables, restored_market, architecture_state, structure_state, flow_state, diffusion_state = apply_synthesized_world_view(
        snapshot=snapshot,
        fallback_user_observables={},
        fallback_market_snapshot=market,
        fallback_architecture_state={},
        fallback_structure_state={},
        fallback_flow_state={},
        fallback_diffusion_state={},
    )

    assert user_observables["intent_index"] == 0.8
    assert restored_market.global_competitive_shift == 0.4
    assert restored_market.segment_states[0].segment_key == "core"
    assert architecture_state["global_stability"] == 0.9
    assert structure_state["blast_radius_risk"] == 0.1
    assert flow_state["velocity"] == 0.4
    assert diffusion_state["spread_index"] == 0.2
