from __future__ import annotations

from crm.crm_lead_contract import CrmLead
from crm.leads.crm_lead_enrichment_policy import CrmLeadEnrichmentPolicy
from crm.leads.crm_lead_normalization_contract import RawLeadPayload
from crm.leads.crm_lead_normalizer import CrmLeadNormalizer
from crm.leads.crm_lead_quality_policy import CrmLeadQualityPolicy
from crm.leads.crm_lead_validation_policy import CrmLeadValidationPolicy


class CrmLeadIngestionService:
    def __init__(self, *, normalizer: CrmLeadNormalizer | None = None, enrichment_policy: CrmLeadEnrichmentPolicy | None = None, validation_policy: CrmLeadValidationPolicy | None = None, quality_policy: CrmLeadQualityPolicy | None = None) -> None:
        self._normalizer = normalizer or CrmLeadNormalizer()
        self._enrichment_policy = enrichment_policy or CrmLeadEnrichmentPolicy()
        self._validation_policy = validation_policy or CrmLeadValidationPolicy()
        self._quality_policy = quality_policy or CrmLeadQualityPolicy()

    def ingest(self, raw: RawLeadPayload) -> tuple[CrmLead, int]:
        lead = self._normalizer.normalize(raw)
        lead = self._enrichment_policy.apply(lead)
        self._validation_policy.validate(lead)
        return lead, self._quality_policy.score(lead)
