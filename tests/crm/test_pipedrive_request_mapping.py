from crm.crm_contact_contract import CrmContact
from crm.crm_identity_contract import CrmIdentity
from crm.providers.pipedrive.pipedrive_contact_adapter import PipedriveContactAdapter


class _FakeClient:
    def __init__(self):
        self.calls = []

    def send(self, request):
        self.calls.append(request)
        if request.path.endswith('/search'):
            return type('Resp', (), {'json_body': {'data': {'items': []}}})()
        return type('Resp', (), {'json_body': {'data': {'id': 42}}})()


class _FakeAuthAdapter:
    def __init__(self, client):
        self.client = client

    def authorized_client(self, *, secret_ref: str, company_domain: str):
        assert secret_ref == 'secret://pipedrive'
        assert company_domain == 'example'
        return self.client


def test_pipedrive_live_contact_mapping_uses_search_then_create():
    fake_client = _FakeClient()
    adapter = PipedriveContactAdapter(auth_adapter=_FakeAuthAdapter(fake_client))
    payload = adapter.upsert(
        contact=CrmContact(contact_id='c1', full_name='Ada Lovelace', identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com', phone='+1')),
        secret_ref='secret://pipedrive',
        company_domain='example',
        idempotency_key='idemp-1',
    )
    assert payload['record_id'] == '42'
    assert fake_client.calls[0].path == '/persons/search'
    assert fake_client.calls[1].path == '/persons'
    assert fake_client.calls[1].json_body['name'] == 'Ada Lovelace'
