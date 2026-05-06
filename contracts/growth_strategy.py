from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GrowthStrategy:
    strategy_id: str = ''
    summary: str = ''
    objective: str = ''
