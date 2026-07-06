from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core.behavior.contracts.segment_field import SegmentField


@dataclass(frozen=True)
class MarketField:
    market_id: str
    segment_fields: tuple[SegmentField, ...]
    observables: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
