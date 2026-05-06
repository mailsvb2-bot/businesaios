from __future__ import annotations

from crm.crm_lead_contract import CrmLead


class CrmLeadValidationPolicy:
    def validate(self, lead: CrmLead) -> None:
        if not lead.identity or not lead.identity.canonical_key:
            raise ValueError('CRM lead must have a canonical identity key')
        if not (lead.email or lead.phone or lead.company_name):
            raise ValueError('CRM lead must contain at least one usable identifying signal')
