from crm.crm_contact_contract import CrmContact
from crm.crm_identity_contract import CrmIdentity
from crm.crm_verification_contract import CrmVerificationRequest
from crm.verification.crm_write_verifier import CrmWriteVerifier


def test_write_verifier_uses_provider_readback(hubspot_connector, connection):
    payload = hubspot_connector.upsert_contact(
        connection,
        CrmContact(
            contact_id='contact-1',
            full_name='Ada Lovelace',
            identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com'),
        ),
        idempotency_key='contact-1',
    )
    result = CrmWriteVerifier().verify(
        hubspot_connector,
        connection,
        CrmVerificationRequest(
            entity_type='contact',
            provider_key='hubspot',
            record_id=str(payload['record_id']),
            expected_fields={'email': 'ada@example.com'},
        ),
    )
    assert result.verified is True
