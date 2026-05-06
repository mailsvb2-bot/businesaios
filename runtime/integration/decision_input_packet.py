from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract


@dataclass(frozen=True)
class DecisionInputPacket:
    recommendation_packet: RecommendationPacketContract

    def as_dict(self) -> dict[str, object]:
        return {
            "recommendation_packet": self.recommendation_packet.as_dict(),
        }
