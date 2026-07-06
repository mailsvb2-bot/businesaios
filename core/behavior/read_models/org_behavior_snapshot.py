from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from core.behavior.assemblers.org_field_assembler import assemble_org_field
from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.builders.event_spinor_builder import build_event_spinor


def build_org_behavior_snapshot(org_id: str, events: list[Mapping[str, Any]]) -> dict[str, object]:
    grouped: dict[str, list] = defaultdict(list)
    for event in events:
        if str(event.get("org_id", "")) != org_id:
            continue
        role = str(event.get("actor_role", "user"))
        grouped[role].append(build_event_spinor(event))
    role_fields = {role: assemble_person_field(f"{org_id}:{role}", spinors) for role, spinors in grouped.items()}
    org_field = assemble_org_field(org_id, role_fields)
    return {
        "org_id": org_id,
        "role_count": len(role_fields),
        "observables": org_field.observables,
    }
