from __future__ import annotations

from datetime import datetime, timezone

from crm.providers.common.crm_credentials import CrmAccessToken
from crm.providers.common.crm_oauth_token_store import SecretVaultBackedCrmOAuthTokenStore
from security.secret_vault import InMemorySecretVault


def test_vault_backed_oauth_token_store_roundtrip() -> None:
    store = SecretVaultBackedCrmOAuthTokenStore(vault=InMemorySecretVault())
    token = CrmAccessToken(
        access_token='access-1',
        refresh_token='refresh-1',
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        scope=('crm.objects.contacts.write',),
        metadata={'region': 'eu1'},
    )

    store.save(provider_key='hubspot', secret_ref='secret://hubspot/live', token=token)
    loaded = store.load(provider_key='hubspot', secret_ref='secret://hubspot/live')

    assert loaded == token
