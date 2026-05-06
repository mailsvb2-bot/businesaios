from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionBudget:
    max_cost: float
    max_actions: int
