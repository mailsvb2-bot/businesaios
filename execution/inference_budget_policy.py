from __future__ import annotations

from dataclasses import dataclass


CANON_INFERENCE_BUDGET_POLICY = True


@dataclass(frozen=True)
class InferenceBudgetPolicy:
    min_headroom_usd: float = 25.0
    max_burn_rate_usd_per_hour: float = 50.0

    def allows_upgrade(self, *, budget_headroom_usd: float, burn_rate_usd_per_hour: float) -> bool:
        return budget_headroom_usd >= self.min_headroom_usd and burn_rate_usd_per_hour <= self.max_burn_rate_usd_per_hour
