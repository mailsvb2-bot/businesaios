from crm.crm_contact_contract import CrmContact
from crm.crm_identity_contract import CrmIdentity
from crm.upsert.crm_upsert_orchestrator import CrmUpsertOrchestrator


def test_contact_upsert_uses_canonical_identity_for_dedup(hubspot_connector, connection):
    orchestrator = CrmUpsertOrchestrator()
    first = CrmContact(
        contact_id='contact-1',
        full_name='Ada Lovelace',
        identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com'),
    )
    second = CrmContact(
        contact_id='contact-2',
        full_name='Ada Byron',
        identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com'),
    )

    first_result = orchestrator.upsert_contact(hubspot_connector, connection, first, idempotency_key='contact-1')
    second_result = orchestrator.upsert_contact(hubspot_connector, connection, second, idempotency_key='contact-2')

    assert first_result.record_id == second_result.record_id
    assert second_result.metadata['operation'] == 'update'
