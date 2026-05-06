from __future__ import annotations

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from runtime.integration.decision_input_packet import DecisionInputPacket


def build_decision_input_packet(
    packet: RecommendationPacketContract,
) -> DecisionInputPacket:
    return DecisionInputPacket(recommendation_packet=packet)
