from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfitSnapshot:
    snapshot_id: str = ''
    profit: float = 0.0
    period_days: str = ''
