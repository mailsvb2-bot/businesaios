from __future__ import annotations

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract


def build_recommendation_packet(
    *,
    packet_id: str,
    world_state: WorldStateContract,
    recommendations: tuple[dict[str, object], ...],
    explanation_lines: tuple[str, ...],
) -> RecommendationPacketContract:
    return RecommendationPacketContract(
        packet_id=packet_id,
        world_state=world_state,
        recommendations=recommendations,
        explanation_lines=explanation_lines,
    )
