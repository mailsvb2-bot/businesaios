from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_contact_contract import CrmContact
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig


class HubSpotContactAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: HubSpotAuthAdapter | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or HubSpotApiConfig()

    def upsert(self, connection: CrmConnectionRef | None = None, contact: CrmContact | None = None, *, secret_ref: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert contact is not None
        if self._auth_adapter is None or not secret_ref:
            assert connection is not None and self._store is not None
            dedup_key = contact.identity.canonical_key or contact.contact_id
            return self._store.upsert_contact(connection, {'contact_id': contact.contact_id, 'full_name': contact.full_name, 'email': contact.identity.email, 'phone': contact.identity.phone, 'canonical_key': contact.identity.canonical_key, 'owner_id': contact.owner_id, 'custom_fields': dict(contact.custom_fields)}, dedup_key=dedup_key, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref)
        existing_id = None
        if contact.identity.email:
            search = client.send(CrmHttpRequest(method='POST', path='/crm/v3/objects/contacts/search', json_body={'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': contact.identity.email}]}], 'limit': 1}))
            payload = search.json_body if isinstance(search.json_body, dict) else {}
            results = payload.get('results', []) if isinstance(payload.get('results'), list) else []
            if results and isinstance(results[0], dict):
                existing_id = str(results[0].get('id') or '') or None
        properties = {'firstname': contact.full_name.split()[0] if contact.full_name else '', 'lastname': ' '.join(contact.full_name.split()[1:]) if contact.full_name and len(contact.full_name.split()) > 1 else '', 'email': contact.identity.email or '', 'phone': contact.identity.phone or ''}
        properties.update({str(k): v for k, v in contact.custom_fields.items()})
        if existing_id:
            response = client.send(CrmHttpRequest(method='PATCH', path=f'/crm/v3/objects/contacts/{existing_id}', json_body={'properties': properties}))
        else:
            response = client.send(CrmHttpRequest(method='POST', path='/crm/v3/objects/contacts', json_body={'properties': properties}))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        return {'operation': 'update' if existing_id else 'create', 'record_id': str(payload.get('id') or existing_id or contact.contact_id), 'dedup_key': contact.identity.canonical_key or contact.contact_id, 'idempotency_key': idempotency_key}
