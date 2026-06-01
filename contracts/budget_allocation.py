from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetAllocation:
    channel: str = ''
    amount: float = 0.0
    share: float = 0.0
