from __future__ import annotations

from crm.crm_lead_contract import CrmLead


class CrmLeadEnrichmentPolicy:
    def apply(self, lead: CrmLead) -> CrmLead:
        return CrmLead(
            **{
                **lead.__dict__,
                'custom_fields': {
                    **dict(lead.custom_fields),
                    'normalized_company_name': (lead.company_name or '').strip().casefold(),
                },
            }
        )
