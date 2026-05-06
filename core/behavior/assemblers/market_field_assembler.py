from __future__ import annotations

from core.behavior.contracts.market_field import MarketField
from core.behavior.contracts.segment_field import SegmentField
from core.behavior.observables.market_observables import compute_market_observables


def assemble_market_field(market_id: str, segment_fields: list[SegmentField]) -> MarketField:
    observables = compute_market_observables(segment_fields)
    return MarketField(
        market_id=market_id,
        segment_fields=tuple(segment_fields),
        observables=observables,
    )
