from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

_MAPPING_FIELDS = ("user_state", "market_state", "creative_state", "architecture_state", "structure_state", "flow_state", "diffusion_state", "economics_state", "reward_state")


@dataclass(frozen=True)
class DecisionContextProjection:
    """Advisory decision-input projection; never the sovereign WorldState."""
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
        mapped = {name: dict(getattr(self, name)) for name in _MAPPING_FIELDS}
        return {"state_id": self.state_id, "generated_at_ms": self.generated_at_ms,
                **mapped, "advisory_flags": dict(self.advisory_flags), "notes": tuple(self.notes)}
