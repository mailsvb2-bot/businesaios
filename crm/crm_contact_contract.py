from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from crm.crm_identity_contract import CrmIdentity


@dataclass(frozen=True)
class CrmContact:
    contact_id: str
    full_name: str | None
    identity: CrmIdentity
    owner_id: str | None = None
    custom_fields: Mapping[str, object] = field(default_factory=dict)
