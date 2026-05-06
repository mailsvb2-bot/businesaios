from __future__ import annotations

from crm.crm_identity_contract import CrmIdentity
from crm.crm_lead_contract import CrmLead


class CrmLeadIdentityResolver:
    def resolve(self, lead: CrmLead) -> CrmIdentity:
        if lead.identity:
            return lead.identity
        return CrmIdentity(canonical_key=lead.email or lead.phone or lead.lead_id, email=lead.email, phone=lead.phone)
