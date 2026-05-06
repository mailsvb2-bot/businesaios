from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_contact_contract import CrmContact
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


class PipedriveContactAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def upsert(self, connection: CrmConnectionRef | None = None, contact: CrmContact | None = None, *, secret_ref: str | None = None, company_domain: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert contact is not None
        if self._auth_adapter is None or not secret_ref or not company_domain:
            assert connection is not None and self._store is not None
            dedup_key = contact.identity.canonical_key or contact.contact_id
            return self._store.upsert_contact(connection, {'contact_id': contact.contact_id, 'full_name': contact.full_name, 'email': contact.identity.email, 'phone': contact.identity.phone, 'canonical_key': contact.identity.canonical_key, 'owner_id': contact.owner_id, 'custom_fields': dict(contact.custom_fields)}, dedup_key=dedup_key, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref, company_domain=company_domain)
        existing_id = None
        if contact.identity.email:
            search = client.send(CrmHttpRequest(method='GET', path='/persons/search', query_params={'term': contact.identity.email, 'fields': 'email', 'exact_match': 1}))
            payload = search.json_body if isinstance(search.json_body, dict) else {}
            items = payload.get('data', {}).get('items', []) if isinstance(payload.get('data'), dict) else []
            if items and isinstance(items[0], dict):
                item = items[0].get('item') if isinstance(items[0].get('item'), dict) else items[0]
                existing_id = str(item.get('id') or '') or None
        body = {'name': contact.full_name, 'email': [contact.identity.email] if contact.identity.email else [], 'phone': [contact.identity.phone] if contact.identity.phone else []}
        body.update({str(k): v for k, v in contact.custom_fields.items()})
        if existing_id:
            response = client.send(CrmHttpRequest(method='PATCH', path=f'/persons/{existing_id}', json_body=body))
        else:
            response = client.send(CrmHttpRequest(method='POST', path='/persons', json_body=body))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        return {'operation': 'update' if existing_id else 'create', 'record_id': str(data.get('id') or existing_id or contact.contact_id), 'dedup_key': contact.identity.canonical_key or contact.contact_id, 'idempotency_key': idempotency_key}
