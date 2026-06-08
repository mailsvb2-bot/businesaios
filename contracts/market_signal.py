from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSignal:
    signal_id: str = ''
    market: str = ''
    demand_score: float = 0.0
