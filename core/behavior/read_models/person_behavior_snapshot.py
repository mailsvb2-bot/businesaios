from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.behavior.adapters.decisioncore_adapter import build_decisioncore_behavior_payload
from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.builders.event_spinor_builder import build_event_spinor


def build_person_behavior_snapshot(entity_id: str, events: list[Mapping[str, Any]]) -> dict[str, object]:
    micro_spinors = [build_event_spinor(event) for event in events if str(event.get("entity_id", entity_id)) == entity_id]
    field = assemble_person_field(entity_id, micro_spinors)
    payload = build_decisioncore_behavior_payload(field.dynamic_observables)
    return {
        "entity_id": entity_id,
        "micro_spinor_count": len(micro_spinors),
        "observables": field.dynamic_observables,
        "payload": payload,
    }
