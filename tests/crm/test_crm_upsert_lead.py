from crm.upsert.crm_lead_upsert_service import CrmLeadUpsertService


def test_lead_upsert_service_maps_lead_to_contact(sample_lead):
    contact = CrmLeadUpsertService().lead_to_contact(sample_lead)
    assert contact.identity.email == 'ada@example.com'
