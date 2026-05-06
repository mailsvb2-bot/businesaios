from __future__ import annotations

from dataclasses import dataclass


CANON_GOVERNANCE_INFERENCE_RUNWAY_GUARD = True


@dataclass(frozen=True)
class InferenceRunwayGuard:
    min_days_remaining: int = 30

    def allows(self, *, runway_days_remaining: int) -> bool:
        return int(runway_days_remaining) >= self.min_days_remaining
