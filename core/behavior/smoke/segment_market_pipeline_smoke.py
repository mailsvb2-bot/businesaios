from __future__ import annotations

from core.behavior.assemblers.market_field_assembler import assemble_market_field
from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.assemblers.segment_field_assembler import assemble_segment_field
from core.behavior.builders.event_spinor_builder import build_event_spinor


def run_segment_market_pipeline_smoke() -> dict[str, object]:
    p1 = assemble_person_field(
        "u1",
        [
            build_event_spinor({"event_id": "1", "entity_id": "u1", "event_type": "message_open"}),
            build_event_spinor({"event_id": "2", "entity_id": "u1", "event_type": "content_engage"}),
        ],
    )
    p2 = assemble_person_field(
        "u2",
        [
            build_event_spinor({"event_id": "3", "entity_id": "u2", "event_type": "price_view"}),
        ],
    )
    segment = assemble_segment_field("segment-a", [p1, p2])
    market = assemble_market_field("market-a", [segment])
    return {
        "segment": segment.observables,
        "market": market.observables,
    }
