from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetAllocator:
    """Budget allocator for the 7d sprint.

    For MVP: constant daily budget = total/7 (rounded down).
    """

    def daily_from_total(self, *, total_minor_7d: int) -> int:
        try:
            total = int(total_minor_7d or 0)
        except Exception:
            total = 0
        return max(0, total // 7)
