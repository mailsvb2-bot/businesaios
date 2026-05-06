from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentTrendState:
    segment_key: str
    macro_score: float
    micro_score: float
    persistence_score: float
    competitive_shift_score: float
