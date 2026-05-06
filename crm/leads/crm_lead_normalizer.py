from __future__ import annotations

from crm.crm_identity_contract import CrmIdentity
from crm.crm_lead_contract import CrmLead
from crm.crm_source_contract import CrmSource
from crm.leads.crm_lead_normalization_contract import RawLeadPayload


class CrmLeadNormalizer:
    def normalize(self, raw: RawLeadPayload) -> CrmLead:
        payload = dict(raw.payload)
        email = str(payload.get('email') or '').strip() or None
        phone = str(payload.get('phone') or '').strip() or None
        source_key = str(payload.get('source_key') or 'unknown')
        return CrmLead(
            lead_id=str(payload.get('lead_id') or payload.get('id') or 'lead:unknown'),
            tenant_id=raw.tenant_id,
            business_id=raw.business_id,
            full_name=str(payload.get('full_name') or payload.get('name') or '') or None,
            email=email,
            phone=phone,
            company_name=str(payload.get('company_name') or payload.get('company') or '') or None,
            desired_stage_key=str(payload.get('desired_stage_key') or '') or None,
            source=CrmSource(source_key=source_key, display_name=source_key.replace('_', ' ').title(), channel=str(payload.get('channel') or source_key)),
            identity=CrmIdentity(canonical_key=email or phone or str(payload.get('external_id') or 'unknown'), email=email, phone=phone),
            custom_fields=payload,
        )
