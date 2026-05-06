from __future__ import annotations

from crm.crm_lead_contract import CrmLead


class CrmDedupKeyBuilder:
    def lead_key(self, lead: CrmLead) -> str:
        identity = lead.identity.canonical_key if lead.identity else lead.lead_id
        return f"lead:{lead.tenant_id}:{lead.business_id}:{identity.strip().casefold()}"
