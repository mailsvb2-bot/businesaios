from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_note_contract import CrmNote
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


class PipedriveNoteAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def append(self, connection: CrmConnectionRef | None = None, note: CrmNote | None = None, *, secret_ref: str | None = None, company_domain: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert note is not None
        if self._auth_adapter is None or not secret_ref or not company_domain:
            assert connection is not None and self._store is not None
            return self._store.append_note(connection, {'body': note.body, 'related_record_id': note.related_record_id, 'related_entity_type': note.related_entity_type}, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref, company_domain=company_domain)
        response = client.send(CrmHttpRequest(method='POST', path='/notes', json_body={'content': note.body, f'{note.related_entity_type}_id': note.related_record_id}))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        return {'operation': 'append', 'record_id': str(data.get('id') or idempotency_key), 'idempotency_key': idempotency_key}
