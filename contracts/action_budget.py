from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionBudget:
    currency: str = ''
    amount: float = 0.0
    daily_cap: float = 0.0
