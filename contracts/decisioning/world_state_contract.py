from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class WorldStateContract:
    state_id: str
    generated_at_ms: int
    user_state: Mapping[str, float]
    market_state: Mapping[str, float]
    creative_state: Mapping[str, float]
    architecture_state: Mapping[str, float]
    structure_state: Mapping[str, float]
    flow_state: Mapping[str, float]
    diffusion_state: Mapping[str, float]
    economics_state: Mapping[str, float]
    reward_state: Mapping[str, float]
    advisory_flags: Mapping[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "generated_at_ms": self.generated_at_ms,
            "user_state": dict(self.user_state),
            "market_state": dict(self.market_state),
            "creative_state": dict(self.creative_state),
            "architecture_state": dict(self.architecture_state),
            "structure_state": dict(self.structure_state),
            "flow_state": dict(self.flow_state),
            "diffusion_state": dict(self.diffusion_state),
            "economics_state": dict(self.economics_state),
            "reward_state": dict(self.reward_state),
            "advisory_flags": dict(self.advisory_flags),
            "notes": tuple(self.notes),
        }
