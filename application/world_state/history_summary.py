from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistorySummary:
    sample_count: int
    scalarized_reward_delta: float
    top_expected_value_delta: float

    def as_dict(self) -> dict[str, float]:
        return {
            "sample_count": float(self.sample_count),
            "scalarized_reward_delta": float(self.scalarized_reward_delta),
            "top_expected_value_delta": float(self.top_expected_value_delta),
        }
