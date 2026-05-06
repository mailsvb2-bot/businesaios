from __future__ import annotations

from core.behavior.contracts.person_field import PersonField
from core.behavior.contracts.segment_field import SegmentField
from core.behavior.observables.segment_observables import compute_segment_observables


def assemble_segment_field(segment_id: str, person_fields: list[PersonField]) -> SegmentField:
    observables = compute_segment_observables(person_fields)
    return SegmentField(
        segment_id=segment_id,
        person_fields=tuple(person_fields),
        observables=observables,
    )
