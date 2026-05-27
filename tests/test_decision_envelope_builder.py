from __future__ import annotations

from application.decision_input.decision_envelope_builder import build_decision_envelope
from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract


def test_decision_envelope_builder_extracts_features() -> None:
    packet = RecommendationPacketContract(
        packet_id="p1",
        world_state=WorldStateContract(
            state_id="s1",
            generated_at_ms=1,
            user_state={"intent": 0.6},
            market_state={"global_macro_score": 0.5},
            creative_state={"top_expected_value_score": 0.4},
            architecture_state={"global_stability": 0.8},
            structure_state={"curvature": 0.2},
            flow_state={"turbulence": 0.1},
            diffusion_state={"viral_potential": 0.3},
            economics_state={"portfolio_roi_mean": 0.2},
            reward_state={"scalarized_value": 0.4},
            advisory_flags={"packet_name": "advisory_v1"},
            notes=(),
        ),
        recommendations=(
            {
                "kind": "autonomy_advisory",
                "phase": "scale",
                "expected_value_score": 0.3,
                "downside_envelope": 0.2,
            },
        ),
        explanation_lines=("hello",),
    )
    envelope = build_decision_envelope(packet)
    assert envelope.world_state_features["user.intent"] == 0.6
    assert envelope.advisory_features["advisory.scale_pressure"] == 1.0
