from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.behavior.contracts.person_field import PersonField


@dataclass(frozen=True)
class OrgField:
    org_id: str
    role_fields: Mapping[str, PersonField]
    observables: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
