from __future__ import annotations

from core.behavior.assemblers.market_field_assembler import assemble_market_field
from core.behavior.contracts.segment_field import SegmentField


def build_market_field(market_id: str, segment_fields: list[SegmentField]) -> object:
    return assemble_market_field(market_id, segment_fields)
