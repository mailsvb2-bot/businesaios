from __future__ import annotations

import json
from collections.abc import Mapping

from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest
from crm.providers.common.crm_http_errors import CrmResponseError
from crm.providers.common.crm_retry_policy import CrmRetryPolicy


class AmoCrmClient:
    def __init__(
        self,
        *,
        account_base_url: str,
        access_token: str,
        timeout_seconds: float = 20.0,
        http_client: CrmHttpClient | None = None,
    ) -> None:
        token = access_token.strip()
        if not token:
            raise ValueError('amoCRM access token must not be blank')
        self._timeout = timeout_seconds
        default_headers = {'Authorization': f'Bearer {token}'}
        self._read_http = http_client or CrmHttpClient(
            base_url=account_base_url,
            default_headers=default_headers,
        )
        self._write_http = http_client or CrmHttpClient(
            base_url=account_base_url,
            default_headers=default_headers,
            retry_policy=CrmRetryPolicy(max_attempts=1),
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        query_params: Mapping[str, object] | None = None,
        body: object | None = None,
    ) -> object | None:
        raw_body = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
        transport = self._read_http if method.upper() == 'GET' else self._write_http
        response = transport.send(
            CrmHttpRequest(
                method=method,
                path=path,
                query_params=dict(query_params or {}),
                headers={'Content-Type': 'application/json'} if raw_body is not None else {},
                raw_body=raw_body,
                timeout_seconds=self._timeout,
            )
        )
        return response.json_body

    def account_info(self) -> dict[str, object]:
        payload = self._send('GET', '/api/v4/account')
        return dict(payload) if isinstance(payload, Mapping) else {}

    def get_contact(self, record_id: str) -> dict[str, object] | None:
        try:
            payload = self._send('GET', f'/api/v4/contacts/{record_id}')
        except CrmResponseError as exc:
            if exc.context.status_code == 404:
                return None
            raise
        return dict(payload) if isinstance(payload, Mapping) else None

    def search_contacts(self, query: str, *, limit: int = 50) -> tuple[dict[str, object], ...]:
        value = query.strip()
        if not value:
            return ()
        payload = self._send('GET', '/api/v4/contacts', query_params={'query': value, 'limit': limit})
        embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
        rows = embedded.get('contacts') if isinstance(embedded, Mapping) else None
        return tuple(dict(row) for row in rows if isinstance(row, Mapping)) if isinstance(rows, list) else ()

    def list_contact_custom_fields(self, *, max_pages: int = 20) -> tuple[dict[str, object], ...]:
        if max_pages <= 0:
            raise ValueError('max_pages must be positive')
        collected: list[dict[str, object]] = []
        for page in range(1, max_pages + 1):
            payload = self._send(
                'GET',
                '/api/v4/contacts/custom_fields',
                query_params={'page': page, 'limit': 250},
            )
            embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
            rows = embedded.get('custom_fields') if isinstance(embedded, Mapping) else None
            if not isinstance(rows, list) or not rows:
                break
            page_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
            collected.extend(page_rows)
            if not page_rows:
                break
        else:
            raise RuntimeError('amoCRM contact custom field pagination exceeded safety bound')
        return tuple(collected)

    def create_contact(self, fields: Mapping[str, object]) -> dict[str, object]:
        payload = self._send('POST', '/api/v4/contacts', body=[dict(fields)])
        embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
        rows = embedded.get('contacts') if isinstance(embedded, Mapping) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
            raise RuntimeError('amoCRM create contact response is missing contact record')
        return dict(rows[0])

    def update_contact(self, record_id: str, fields: Mapping[str, object]) -> dict[str, object]:
        payload = self._send('PATCH', f'/api/v4/contacts/{record_id}', body=dict(fields))
        if isinstance(payload, Mapping):
            return dict(payload)
        return {'id': record_id}

    def get_lead(self, record_id: str) -> dict[str, object] | None:
        try:
            payload = self._send('GET', f'/api/v4/leads/{record_id}')
        except CrmResponseError as exc:
            if exc.context.status_code == 404:
                return None
            raise
        return dict(payload) if isinstance(payload, Mapping) else None

    def create_lead(self, fields: Mapping[str, object]) -> dict[str, object]:
        payload = self._send('POST', '/api/v4/leads', body=[dict(fields)])
        embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
        rows = embedded.get('leads') if isinstance(embedded, Mapping) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
            raise RuntimeError('amoCRM create lead response is missing lead record')
        return dict(rows[0])

    def update_lead(self, record_id: str, fields: Mapping[str, object]) -> dict[str, object]:
        payload = self._send('PATCH', f'/api/v4/leads/{record_id}', body=dict(fields))
        if isinstance(payload, Mapping):
            return dict(payload)
        return {'id': record_id}

    def link_contact_to_lead(
        self,
        *,
        lead_id: str,
        contact_id: str,
        is_main: bool = True,
    ) -> dict[str, object]:
        lead_text = str(lead_id or '').strip()
        contact_text = str(contact_id or '').strip()
        if not lead_text.isdigit() or int(lead_text) <= 0:
            raise ValueError('amoCRM lead ID for relation must be a positive integer')
        if not contact_text.isdigit() or int(contact_text) <= 0:
            raise ValueError('amoCRM contact ID for relation must be a positive integer')
        payload = self._send(
            'POST',
            f'/api/v4/leads/{lead_text}/link',
            body=[
                {
                    'to_entity_id': int(contact_text),
                    'to_entity_type': 'contacts',
                    'metadata': {'is_main': bool(is_main)},
                }
            ],
        )
        return dict(payload) if isinstance(payload, Mapping) else {}

    def list_pipelines(self) -> tuple[dict[str, object], ...]:
        payload = self._send('GET', '/api/v4/leads/pipelines')
        embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
        rows = embedded.get('pipelines') if isinstance(embedded, Mapping) else None
        return tuple(dict(row) for row in rows if isinstance(row, Mapping)) if isinstance(rows, list) else ()

    def append_common_note(self, *, entity_type: str, entity_id: str, text: str) -> dict[str, object]:
        if entity_type not in {'contacts', 'leads'}:
            raise ValueError('amoCRM note entity type must be contacts or leads')
        if not text.strip():
            raise ValueError('amoCRM note text must not be blank')
        payload = self._send(
            'POST',
            f'/api/v4/{entity_type}/{entity_id}/notes',
            body=[{'note_type': 'common', 'params': {'text': text}}],
        )
        embedded = payload.get('_embedded') if isinstance(payload, Mapping) else None
        rows = embedded.get('notes') if isinstance(embedded, Mapping) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
            raise RuntimeError('amoCRM append note response is missing note record')
        return dict(rows[0])
