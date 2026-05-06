from crm.upsert.crm_upsert_orchestrator import CrmUpsertOrchestrator


def test_deal_upsert_verifies_write(hubspot_connector, connection, sample_deal):
    result = CrmUpsertOrchestrator().upsert_deal(hubspot_connector, connection, sample_deal, idempotency_key='deal-1')
    assert result.verified is True
