from __future__ import annotations

from crm.crm_lead_contract import CrmLead


class CrmLeadStageResolver:
    def resolve(self, lead: CrmLead) -> str:
        return lead.desired_stage_key or 'new'
