from __future__ import annotations

from crm.crm_contact_contract import CrmContact
from crm.crm_identity_contract import CrmIdentity
from crm.crm_lead_contract import CrmLead


class CrmLeadUpsertService:
    def lead_to_contact(self, lead: CrmLead) -> CrmContact:
        identity = lead.identity or CrmIdentity(canonical_key=lead.email or lead.phone or lead.lead_id, email=lead.email, phone=lead.phone)
        return CrmContact(contact_id=lead.lead_id, full_name=lead.full_name, identity=identity, custom_fields=lead.custom_fields)
