from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_note_contract import CrmNote
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter


class HubSpotNoteAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: HubSpotAuthAdapter | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or HubSpotApiConfig()

    def append(self, connection: CrmConnectionRef | None = None, note: CrmNote | None = None, *, secret_ref: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert note is not None
        if self._auth_adapter is None or not secret_ref:
            assert connection is not None and self._store is not None
            return self._store.append_note(connection, {'body': note.body, 'related_record_id': note.related_record_id, 'related_entity_type': note.related_entity_type}, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref)
        response = client.send(CrmHttpRequest(method='POST', path='/crm/v3/objects/notes', json_body={'properties': {'hs_note_body': note.body}}))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        return {'operation': 'append', 'record_id': str(payload.get('id') or idempotency_key), 'idempotency_key': idempotency_key}
