from __future__ import annotations

from crm.providers.common.crm_http_client import CrmHttpClient
from crm.providers.common.crm_oauth_service import CrmOAuthProviderConfig, CrmOAuthService
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig


class HubSpotAuthAdapter:
    def __init__(self, *, token_store: CrmOAuthTokenStore, client_id: str, client_secret: str, api_config: HubSpotApiConfig | None = None) -> None:
        self._api_config = api_config or HubSpotApiConfig()
        self._oauth_service = CrmOAuthService(
            http_client_factory=lambda base_url: CrmHttpClient(base_url=base_url),
            token_store=token_store,
        )
        self._provider_config = CrmOAuthProviderConfig(
            provider_key='hubspot',
            token_url=f'{self._api_config.oauth_base_url}/oauth/v1/token',
            client_id=client_id,
            client_secret=client_secret,
        )

    def exchange_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str):
        return self._oauth_service.exchange_code(config=self._provider_config, secret_ref=secret_ref, authorization_code=authorization_code, redirect_uri=redirect_uri)

    def authorized_client(self, *, secret_ref: str) -> CrmHttpClient:
        token = self._oauth_service.ensure_active_token(config=self._provider_config, secret_ref=secret_ref)
        return CrmHttpClient(base_url=self._api_config.base_url, default_headers={'Authorization': f'Bearer {token.access_token}'})


    def revoke_binding(self, *, secret_ref: str) -> None:
        self._oauth_service.revoke_binding(config=self._provider_config, secret_ref=secret_ref)
