from __future__ import annotations

from core.behavior.assemblers.segment_field_assembler import assemble_segment_field
from core.behavior.contracts.person_field import PersonField


def build_segment_field(segment_id: str, person_fields: list[PersonField]) -> object:
    return assemble_segment_field(segment_id, person_fields)
