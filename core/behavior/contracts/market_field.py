from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.behavior.contracts.segment_field import SegmentField


@dataclass(frozen=True)
class MarketField:
    market_id: str
    segment_fields: tuple[SegmentField, ...]
    observables: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
