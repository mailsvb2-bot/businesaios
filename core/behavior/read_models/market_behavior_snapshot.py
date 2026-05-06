from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from core.behavior.assemblers.market_field_assembler import assemble_market_field
from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.assemblers.segment_field_assembler import assemble_segment_field
from core.behavior.builders.event_spinor_builder import build_event_spinor


def build_market_behavior_snapshot(market_id: str, events: list[Mapping[str, Any]]) -> dict[str, object]:
    by_segment: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for event in events:
        if str(event.get("market_id", "")) != market_id:
            continue
        segment_id = str(event.get("segment_id", "default"))
        entity_id = str(event.get("entity_id", "unknown"))
        by_segment[segment_id][entity_id].append(build_event_spinor(event))
    segments = []
    for segment_id, entity_map in by_segment.items():
        person_fields = [assemble_person_field(entity_id, spinors) for entity_id, spinors in entity_map.items()]
        segments.append(assemble_segment_field(segment_id, person_fields))
    market_field = assemble_market_field(market_id, segments)
    return {
        "market_id": market_id,
        "segment_count": len(segments),
        "observables": market_field.observables,
    }
