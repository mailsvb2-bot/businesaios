from __future__ import annotations

from dataclasses import dataclass

from runtime.decisioning import RecommendationSet


@dataclass(frozen=True)
class AutonomyAdvisoryPacket:
    packet_name: str
    recommendations: RecommendationSet
    notes: tuple[str, ...]
