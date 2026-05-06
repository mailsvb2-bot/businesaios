from __future__ import annotations

import pytest

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.decision_input.provider_call import call_decision_input_provider
from runtime.decision_input.runtime_packet_provider import maybe_build_decision_input_packet
from runtime.integration.decision_input_packet import DecisionInputPacket


class _SimpleProvider:
    def build_decision_input_packet(self, *, world_state):
        return DecisionInputPacket(
            recommendation_packet=RecommendationPacketContract(
                packet_id="p1",
                world_state=WorldStateContract(
                    state_id="ws1",
                    generated_at_ms=7,
                    user_state={},
                    market_state={},
                    creative_state={},
                    architecture_state={},
                    structure_state={},
                    flow_state={},
                    diffusion_state={},
                    economics_state={},
                    reward_state={},
                ),
                recommendations=(),
                explanation_lines=(),
            ),
        )


class _RichProvider:
    def build_decision_input_packet(self, *, world_state, proposal, generated_at_ms, safe_mode):
        assert proposal == {"x": 1}
        assert generated_at_ms == 7
        assert safe_mode is True
        return DecisionInputPacket(
            recommendation_packet=RecommendationPacketContract(
                packet_id="p1",
                world_state=WorldStateContract(
                    state_id="ws1",
                    generated_at_ms=7,
                    user_state={},
                    market_state={},
                    creative_state={},
                    architecture_state={},
                    structure_state={},
                    flow_state={},
                    diffusion_state={},
                    economics_state={},
                    reward_state={},
                ),
                recommendations=(),
                explanation_lines=(),
            ),
        )


class _BrokenRichProvider:
    def build_decision_input_packet(self, *, world_state, proposal, generated_at_ms, safe_mode):
        raise TypeError("internal bug must not be swallowed")


def test_call_decision_input_provider_supports_simple_signature():
    packet = call_decision_input_provider(
        build_fn=_SimpleProvider().build_decision_input_packet,
        world_state={"a": 1},
        proposal={"x": 1},
        generated_at_ms=7,
        safe_mode=True,
    )
    assert isinstance(packet, DecisionInputPacket)


def test_call_decision_input_provider_supports_full_signature():
    packet = call_decision_input_provider(
        build_fn=_RichProvider().build_decision_input_packet,
        world_state={"a": 1},
        proposal={"x": 1},
        generated_at_ms=7,
        safe_mode=True,
    )
    assert isinstance(packet, DecisionInputPacket)


def test_maybe_build_decision_input_packet_does_not_hide_internal_type_errors():
    with pytest.raises(TypeError, match="internal bug must not be swallowed"):
        maybe_build_decision_input_packet(
            provider=_BrokenRichProvider(),
            world_state={"a": 1},
            proposal={"x": 1},
            generated_at_ms=7,
            safe_mode=True,
        )
