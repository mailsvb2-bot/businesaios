from __future__ import annotations

from core.behavior.contracts.org_field import OrgField
from core.behavior.contracts.person_field import PersonField
from core.behavior.observables.org_observables import compute_org_observables


def assemble_org_field(org_id: str, role_fields: dict[str, PersonField]) -> OrgField:
    observables = compute_org_observables(role_fields)
    return OrgField(
        org_id=org_id,
        role_fields=role_fields,
        observables=observables,
    )
