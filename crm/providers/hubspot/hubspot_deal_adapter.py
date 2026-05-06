from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_deal_contract import CrmDeal
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig


class HubSpotDealAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: HubSpotAuthAdapter | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or HubSpotApiConfig()

    def upsert(self, connection: CrmConnectionRef | None = None, deal: CrmDeal | None = None, *, secret_ref: str | None = None, idempotency_key: str) -> dict[str, object]:
        assert deal is not None
        if self._auth_adapter is None or not secret_ref:
            assert connection is not None and self._store is not None
            dedup_key = deal.deal_id
            return self._store.upsert_deal(connection, {'deal_id': deal.deal_id, 'title': deal.title, 'pipeline_key': deal.pipeline_key, 'stage_key': deal.stage_key, 'value': str(deal.value) if deal.value is not None else None, 'currency': deal.currency, 'owner_id': deal.owner_id, 'contact_id': deal.contact_id, 'custom_fields': dict(deal.custom_fields), 'is_closed': deal.stage_key.lower() in {'won', 'lost', 'closed_won', 'closed_lost'}, 'is_won': deal.stage_key.lower() in {'won', 'closed_won'}, 'is_stale': bool(deal.custom_fields.get('is_stale', False))}, dedup_key=dedup_key, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref)
        provider_record_id = str(deal.custom_fields.get('provider_record_id') or '').strip() or None
        properties = {'dealname': deal.title, 'pipeline': deal.pipeline_key, 'dealstage': deal.stage_key, 'amount': str(deal.value) if deal.value is not None else '', 'hs_currency_code': deal.currency or ''}
        properties.update({str(k): v for k, v in deal.custom_fields.items() if k != 'provider_record_id'})
        if provider_record_id:
            response = client.send(CrmHttpRequest(method='PATCH', path=f'/crm/v3/objects/deals/{provider_record_id}', json_body={'properties': properties}))
        else:
            response = client.send(CrmHttpRequest(method='POST', path='/crm/v3/objects/deals', json_body={'properties': properties}))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        return {'operation': 'update' if provider_record_id else 'create', 'record_id': str(payload.get('id') or provider_record_id or deal.deal_id), 'dedup_key': deal.deal_id, 'idempotency_key': idempotency_key}
