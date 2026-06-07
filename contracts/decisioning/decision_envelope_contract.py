from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping


@dataclass(frozen=True)
class DecisionEnvelopeContract:
    packet_id: str
    world_state_features: Mapping[str, float]
    advisory_features: Mapping[str, float]
    explanation_lines: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "world_state_features": dict(self.world_state_features),
            "advisory_features": dict(self.advisory_features),
            "explanation_lines": tuple(self.explanation_lines),
            "metadata": dict(self.metadata),
        }
