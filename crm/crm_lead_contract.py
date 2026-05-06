from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from crm.crm_identity_contract import CrmIdentity
from crm.crm_source_contract import CrmSource


@dataclass(frozen=True)
class CrmLead:
    lead_id: str
    tenant_id: str
    business_id: str
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    desired_stage_key: str | None = None
    source: CrmSource | None = None
    identity: CrmIdentity | None = None
    custom_fields: Mapping[str, object] = field(default_factory=dict)
