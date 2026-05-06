from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.assemblers.segment_field_assembler import assemble_segment_field
from core.behavior.builders.event_spinor_builder import build_event_spinor


def build_segment_behavior_snapshot(segment_id: str, events: list[Mapping[str, Any]]) -> dict[str, object]:
    grouped: dict[str, list] = defaultdict(list)
    for event in events:
        if str(event.get("segment_id", "")) != segment_id:
            continue
        grouped[str(event.get("entity_id", "unknown"))].append(build_event_spinor(event))
    person_fields = [assemble_person_field(entity_id, spinors) for entity_id, spinors in grouped.items()]
    segment_field = assemble_segment_field(segment_id, person_fields)
    return {
        "segment_id": segment_id,
        "entity_count": len(person_fields),
        "observables": segment_field.observables,
    }
