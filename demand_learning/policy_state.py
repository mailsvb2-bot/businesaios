from __future__ import annotations

from dataclasses import dataclass, field

from shared.numbers import coerce_float


@dataclass(frozen=True)
class PolicyState:
    fairness_boost: dict[str, float] = field(default_factory=dict)
    causal_bonus: dict[str, float] = field(default_factory=dict)
    risk_penalty: dict[str, float] = field(default_factory=dict)
    sample_size: dict[str, int] = field(default_factory=dict)
    last_updated_from_rows: int = 0

    def adjustment_for(self, business_id: str) -> float:
        bid = str(business_id)
        return (
            coerce_float(self.fairness_boost.get(bid), 0.0)
            + coerce_float(self.causal_bonus.get(bid), 0.0)
            - coerce_float(self.risk_penalty.get(bid), 0.0)
        )
