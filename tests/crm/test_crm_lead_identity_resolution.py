from crm.leads.crm_lead_identity_resolver import CrmLeadIdentityResolver


def test_lead_identity_resolver_returns_existing_identity(sample_lead):
    assert CrmLeadIdentityResolver().resolve(sample_lead).canonical_key == 'ada@example.com'
