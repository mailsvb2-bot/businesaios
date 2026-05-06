from crm.leads.crm_lead_stage_resolver import CrmLeadStageResolver


def test_lead_stage_defaults_to_new(sample_lead):
    assert CrmLeadStageResolver().resolve(sample_lead) == 'new'
