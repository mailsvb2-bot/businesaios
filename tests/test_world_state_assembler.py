from __future__ import annotations

from contracts.decisioning.reward_signal_contract import RewardSignalContract
from application.world_state.world_state_assembler import assemble_world_state
from runtime.market.market_snapshot import MarketSnapshot


def test_world_state_assembler_builds_contract() -> None:
    world_state = assemble_world_state(
        generated_at_ms=12345,
        user_observables={
            "intent_index": 0.6,
            "trust_index": 0.7,
            "value_index": 0.5,
            "payment_readiness_index": 0.4,
            "fatigue_index": 0.2,
            "hesitation_score": 0.1,
            "buy_vector": 0.55,
            "churn_vector": 0.15,
            "coherence_score": 0.8,
        },
        market_snapshot=MarketSnapshot(
            global_macro_score=0.6,
            global_micro_score=0.55,
            global_competitive_shift=0.3,
            segment_states=(),
        ),
        creative_snapshots=(),
        architecture_state={"global_stability": 0.8},
        structure_state={"curvature": 0.2, "boundary_pressure": 0.3, "blast_radius_risk": 0.25},
        flow_state={"velocity": 0.5, "pressure": 0.4, "turbulence": 0.1},
        diffusion_state={"spread_index": 0.45, "saturation_risk": 0.2, "viral_potential": 0.4},
        reward_signal=RewardSignalContract(
            immediate_reward=0.2,
            expected_future_value=0.3,
            risk_cost=0.1,
            constraint_cost=0.05,
        ),
        advisory_flags={"packet_name": "x"},
        notes=("ok",),
    )
    assert world_state.state_id
    assert world_state.reward_state["scalarized_value"] > 0.0
