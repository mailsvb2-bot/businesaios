from __future__ import annotations

from dataclasses import dataclass

from runtime.market.segment_trend_state import SegmentTrendState


@dataclass(frozen=True)
class MarketSnapshot:
    global_macro_score: float
    global_micro_score: float
    global_competitive_shift: float
    segment_states: tuple[SegmentTrendState, ...]
