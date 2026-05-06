from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScalePolicy:
    """Very conservative scaling policy."""
    max_increase_pct: int = 10

    def next_budget_minor(self, *, current_daily_minor: int, roi_ok: bool) -> int:
        if not roi_ok:
            return int(current_daily_minor)
        inc = max(0, int(current_daily_minor) * int(self.max_increase_pct) // 100)
        return int(current_daily_minor) + int(inc)
