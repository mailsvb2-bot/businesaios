from __future__ import annotations

from crm.crm_lead_contract import CrmLead


class CrmLeadQualityPolicy:
    def score(self, lead: CrmLead) -> int:
        score = 0
        if lead.email:
            score += 40
        if lead.phone:
            score += 35
        if lead.company_name:
            score += 15
        if lead.source and lead.source.source_key != 'unknown':
            score += 10
        return score
