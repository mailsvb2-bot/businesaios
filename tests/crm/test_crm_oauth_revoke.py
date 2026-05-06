from crm.providers.common.crm_credentials import CrmAccessToken
from crm.providers.common.crm_oauth_token_store import InMemoryCrmOAuthTokenStore
from crm.providers.common.crm_oauth_service import CrmOAuthProviderConfig, CrmOAuthService


class _UnusedClient:
    def send(self, request):
        raise AssertionError("send should not be called")


def test_revoke_binding_deletes_token() -> None:
    store = InMemoryCrmOAuthTokenStore()
    service = CrmOAuthService(http_client_factory=lambda base_url: _UnusedClient(), token_store=store)
    config = CrmOAuthProviderConfig(provider_key="hubspot", token_url="https://example/token", client_id="id", client_secret="secret")
    store.save(provider_key="hubspot", secret_ref="ref-1", token=CrmAccessToken(access_token="token"))

    service.revoke_binding(config=config, secret_ref="ref-1")

    assert store.load(provider_key="hubspot", secret_ref="ref-1") is None
