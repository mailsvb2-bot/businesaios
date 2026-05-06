from __future__ import annotations

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.decision_input.runtime_packet_provider import maybe_build_decision_input_packet
from runtime.integration.decision_input_packet import DecisionInputPacket


class _Provider:
    def build_decision_input_packet(self, *, world_state, proposal, generated_at_ms, safe_mode):
        _ = (world_state, proposal, generated_at_ms, safe_mode)
        return DecisionInputPacket(
            recommendation_packet=RecommendationPacketContract(
                packet_id="p1",
                world_state=WorldStateContract(
                    state_id="s1",
                    generated_at_ms=1,
                    user_state={},
                    market_state={},
                    creative_state={},
                    architecture_state={},
                    structure_state={},
                    flow_state={},
                    diffusion_state={},
                    economics_state={},
                    reward_state={},
                    advisory_flags={},
                    notes=(),
                ),
                recommendations=(),
                explanation_lines=(),
            )
        )


def test_runtime_packet_provider_returns_packet() -> None:
    packet = maybe_build_decision_input_packet(
        provider=_Provider(),
        world_state={"x": 1},
        proposal={"kind": "deploy"},
        generated_at_ms=1,
        safe_mode=False,
    )
    assert packet is not None
    assert packet.recommendation_packet.packet_id == "p1"
