from __future__ import annotations

from collections.abc import Mapping

from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest
from crm.providers.common.crm_retry_policy import CrmRetryPolicy


class Bitrix24Client:
    def __init__(
        self,
        *,
        portal_rest_base: str,
        access_token: str,
        timeout_seconds: float = 20.0,
        http_client: CrmHttpClient | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError('Bitrix24 access token must not be blank')
        self._token = access_token.strip()
        self._timeout_seconds = timeout_seconds
        self._read_http = http_client or CrmHttpClient(base_url=portal_rest_base)
        self._write_http = http_client or CrmHttpClient(
            base_url=portal_rest_base,
            retry_policy=CrmRetryPolicy(max_attempts=1),
        )

    @staticmethod
    def _method_path(method: str) -> str:
        normalized = str(method or '').strip().casefold()
        if not normalized or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789._' for char in normalized):
            raise ValueError('Bitrix24 REST method name is invalid')
        return f'/{normalized}.json'

    def call(
        self,
        method: str,
        params: Mapping[str, object] | None = None,
        *,
        retry_safe: bool = False,
    ) -> object:
        body = dict(params or {})
        body['auth'] = self._token
        transport = self._read_http if retry_safe else self._write_http
        response = transport.send(
            CrmHttpRequest(
                method='POST',
                path=self._method_path(method),
                json_body=body,
                timeout_seconds=self._timeout_seconds,
            )
        )
        payload = response.json_body
        if not isinstance(payload, Mapping):
            raise RuntimeError('Bitrix24 REST response is not a JSON object')
        error = str(payload.get('error') or '').strip()
        if error:
            raise RuntimeError(f'Bitrix24 REST request failed: {error}')
        if 'result' not in payload:
            raise RuntimeError('Bitrix24 REST response is missing result')
        return payload['result']

    def probe_crm(self) -> None:
        result = self.call('crm.item.fields', {'entityTypeId': 2}, retry_safe=True)
        if not isinstance(result, Mapping):
            raise RuntimeError('Bitrix24 CRM field probe returned an invalid shape')

    def list_categories(self) -> tuple[Mapping[str, object], ...]:
        result = self.call('crm.category.list', {'entityTypeId': 2}, retry_safe=True)
        rows = result.get('categories') if isinstance(result, Mapping) else None
        if not isinstance(rows, list):
            return ()
        return tuple(row for row in rows if isinstance(row, Mapping))

    def list_stages(self, category_id: int) -> tuple[Mapping[str, object], ...]:
        entity_id = 'DEAL_STAGE' if category_id == 0 else f'DEAL_STAGE_{category_id}'
        result = self.call(
            'crm.status.list',
            {'filter': {'ENTITY_ID': entity_id}, 'order': {'SORT': 'ASC'}},
            retry_safe=True,
        )
        if not isinstance(result, list):
            return ()
        return tuple(row for row in result if isinstance(row, Mapping))

    def get_item(self, *, entity_type_id: int, record_id: str) -> Mapping[str, object] | None:
        if not str(record_id).isdigit():
            raise ValueError('Bitrix24 provider record ID must be numeric')
        result = self.call(
            'crm.item.get',
            {'entityTypeId': entity_type_id, 'id': int(record_id)},
            retry_safe=True,
        )
        item = result.get('item') if isinstance(result, Mapping) else None
        return item if isinstance(item, Mapping) else None

    def create_item(self, *, entity_type_id: int, fields: Mapping[str, object]) -> Mapping[str, object]:
        result = self.call('crm.item.add', {'entityTypeId': entity_type_id, 'fields': dict(fields)})
        item = result.get('item') if isinstance(result, Mapping) else None
        if not isinstance(item, Mapping):
            raise RuntimeError('Bitrix24 create did not return an item')
        return item

    def update_item(self, *, entity_type_id: int, record_id: str, fields: Mapping[str, object]) -> Mapping[str, object]:
        if not str(record_id).isdigit():
            raise ValueError('Bitrix24 provider record ID must be numeric')
        result = self.call(
            'crm.item.update',
            {'entityTypeId': entity_type_id, 'id': int(record_id), 'fields': dict(fields)},
        )
        item = result.get('item') if isinstance(result, Mapping) else None
        if isinstance(item, Mapping):
            return item
        readback = self.get_item(entity_type_id=entity_type_id, record_id=record_id)
        if readback is None:
            raise RuntimeError('Bitrix24 update could not be read back')
        return readback

    def append_timeline_comment(self, *, entity_type: str, entity_id: str, text: str) -> str:
        if not str(entity_id).isdigit():
            raise ValueError('Bitrix24 timeline entity ID must be numeric')
        result = self.call(
            'crm.timeline.comment.add',
            {
                'fields': {
                    'ENTITY_ID': int(entity_id),
                    'ENTITY_TYPE': entity_type,
                    'COMMENT': text,
                }
            },
        )
        record_id = str(result or '').strip()
        if not record_id.isdigit():
            raise RuntimeError('Bitrix24 timeline comment did not return an ID')
        return record_id
