from crm.leads.crm_lead_normalization_contract import RawLeadPayload
from crm.leads.crm_lead_normalizer import CrmLeadNormalizer


def test_lead_normalization_maps_basic_fields():
    lead = CrmLeadNormalizer().normalize(RawLeadPayload(tenant_id='t', business_id='b', payload={'name': 'Ada', 'email': 'ada@example.com'}))
    assert lead.identity.canonical_key == 'ada@example.com'
