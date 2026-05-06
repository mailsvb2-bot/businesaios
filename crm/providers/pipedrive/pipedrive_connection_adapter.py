from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


class ProviderConnectionAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        if self._auth_adapter is None or not connection.secret_ref:
            if self._store is None:
                return {'verified': False, 'provider_key': 'pipedrive', 'reason': 'missing_store'}
            return self._store.verify_connection(connection)
        company_domain = str(connection.metadata.get('company_domain') or '').strip()
        if not company_domain:
            return {'verified': False, 'provider_key': 'pipedrive', 'reason': 'missing_company_domain'}
        client = self._auth_adapter.authorized_client(secret_ref=connection.secret_ref, company_domain=company_domain)
        response = client.send(CrmHttpRequest(method='GET', path='/users/me'))
        return {'verified': response.status_code < 400, 'provider_key': 'pipedrive', 'reason': 'verified' if response.status_code < 400 else 'api_error'}
