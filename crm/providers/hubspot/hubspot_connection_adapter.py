from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter


class ProviderConnectionAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: HubSpotAuthAdapter | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or HubSpotApiConfig()

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        if self._auth_adapter is None or not connection.secret_ref:
            if self._store is None:
                return {'verified': False, 'provider_key': 'hubspot', 'reason': 'missing_store'}
            return self._store.verify_connection(connection)
        client = self._auth_adapter.authorized_client(secret_ref=connection.secret_ref)
        response = client.send(CrmHttpRequest(method='GET', path='/crm/v3/owners'))
        body = response.json_body if isinstance(response.json_body, dict) else {}
        return {'verified': response.status_code < 400, 'provider_key': 'hubspot', 'reason': 'verified' if response.status_code < 400 else 'api_error', 'owner_count_hint': len(body.get('results', [])) if isinstance(body.get('results'), list) else 0}
