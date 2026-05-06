from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RewardDetails:
    reward: float
    ltv: float | None = None
    spend: float | None = None
    source: str = "advisory_reward_details"


def build_reward_details(*, reward: float, ltv: float | None = None, spend: float | None = None, source: str = "advisory_reward_details") -> RewardDetails:
    return RewardDetails(
        reward=float(reward),
        ltv=float(ltv) if ltv is not None else None,
        spend=float(spend) if spend is not None else None,
        source=str(source),
    )
