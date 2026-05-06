from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_deal_contract import CrmDeal
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


class PipedriveDealAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def upsert(self, connection: CrmConnectionRef | None = None, deal: CrmDeal | None = None, *, secret_ref: str | None = None, company_domain: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert deal is not None
        if self._auth_adapter is None or not secret_ref or not company_domain:
            assert connection is not None and self._store is not None
            return self._store.upsert_deal(connection, {'deal_id': deal.deal_id, 'title': deal.title, 'pipeline_key': deal.pipeline_key, 'stage_key': deal.stage_key, 'value': str(deal.value) if deal.value is not None else None, 'currency': deal.currency, 'owner_id': deal.owner_id, 'contact_id': deal.contact_id, 'custom_fields': dict(deal.custom_fields), 'is_closed': deal.stage_key.lower() in {'won', 'lost', 'closed_won', 'closed_lost'}, 'is_won': deal.stage_key.lower() in {'won', 'closed_won'}, 'is_stale': bool(deal.custom_fields.get('is_stale', False))}, dedup_key=deal.deal_id, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref, company_domain=company_domain)
        provider_record_id = str(deal.custom_fields.get('provider_record_id') or '').strip() or None
        body = {'title': deal.title, 'value': float(deal.value) if deal.value is not None else None, 'currency': deal.currency, 'stage_id': deal.stage_key, 'pipeline_id': deal.pipeline_key, 'person_id': deal.contact_id}
        body.update({str(k): v for k, v in deal.custom_fields.items() if k != 'provider_record_id'})
        if provider_record_id:
            response = client.send(CrmHttpRequest(method='PATCH', path=f'/deals/{provider_record_id}', json_body=body))
        else:
            response = client.send(CrmHttpRequest(method='POST', path='/deals', json_body=body))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        return {'operation': 'update' if provider_record_id else 'create', 'record_id': str(data.get('id') or provider_record_id or deal.deal_id), 'dedup_key': deal.deal_id, 'idempotency_key': idempotency_key}
