from __future__ import annotations

from contracts.decisioning.decision_input_contract import DecisionInputContract
from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from application.decision_input.decision_envelope_builder import build_decision_envelope


def build_decision_input_contract(
    packet: RecommendationPacketContract,
) -> DecisionInputContract:
    return DecisionInputContract(
        envelope=build_decision_envelope(packet),
    )
