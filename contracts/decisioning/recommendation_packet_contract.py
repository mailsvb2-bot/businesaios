from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.decision_context_projection import DecisionContextProjection


@dataclass(frozen=True)
class RecommendationPacketContract:
    packet_id: str
    world_state: DecisionContextProjection
    recommendations: tuple[dict[str, object], ...]
    explanation_lines: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "world_state": self.world_state.as_dict(),
            "recommendations": tuple(dict(item) for item in self.recommendations),
            "explanation_lines": tuple(self.explanation_lines),
        }
