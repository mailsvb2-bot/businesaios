from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BidStrategy:
    strategy_name: str = ''
    target_metric: str = ''
    limit: float = 0.0
