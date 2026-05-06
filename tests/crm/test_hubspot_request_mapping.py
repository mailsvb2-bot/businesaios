from crm.crm_contact_contract import CrmContact
from crm.crm_identity_contract import CrmIdentity
from crm.providers.hubspot.hubspot_contact_adapter import HubSpotContactAdapter


class _FakeClient:
    def __init__(self):
        self.calls = []

    def send(self, request):
        self.calls.append(request)
        if request.path.endswith('/search'):
            return type('Resp', (), {'json_body': {'results': []}})()
        return type('Resp', (), {'json_body': {'id': '123'}})()


class _FakeAuthAdapter:
    def __init__(self, client):
        self.client = client

    def authorized_client(self, *, secret_ref: str):
        assert secret_ref == 'secret://hubspot'
        return self.client


def test_hubspot_live_contact_mapping_uses_search_then_create():
    fake_client = _FakeClient()
    adapter = HubSpotContactAdapter(auth_adapter=_FakeAuthAdapter(fake_client))
    payload = adapter.upsert(
        contact=CrmContact(contact_id='c1', full_name='Ada Lovelace', identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com', phone='+1')),
        secret_ref='secret://hubspot',
        idempotency_key='idemp-1',
    )
    assert payload['record_id'] == '123'
    assert fake_client.calls[0].path == '/crm/v3/objects/contacts/search'
    assert fake_client.calls[1].path == '/crm/v3/objects/contacts'
    assert fake_client.calls[1].json_body['properties']['email'] == 'ada@example.com'
