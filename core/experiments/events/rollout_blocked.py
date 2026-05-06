from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RolloutBlocked:
    experiment_id: str
    reason: str
