from crm.upsert.crm_upsert_orchestrator import CrmUpsertOrchestrator


def test_contact_upsert_verifies_write(hubspot_connector, connection, sample_contact):
    result = CrmUpsertOrchestrator().upsert_contact(hubspot_connector, connection, sample_contact, idempotency_key='contact-1')
    assert result.verified is True
