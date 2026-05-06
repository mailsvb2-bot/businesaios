from __future__ import annotations

from contracts.decisioning.decision_input_contract import DecisionInputContract
from runtime.decision_input import build_decision_input_contract
from runtime.integration.decision_input_packet import DecisionInputPacket


def adapt_packet_for_decision_core(
    packet: DecisionInputPacket,
) -> DecisionInputContract:
    return build_decision_input_contract(packet.recommendation_packet)
