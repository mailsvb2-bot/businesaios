from __future__ import annotations

from security.key_provider_sqlite import SqliteKeyProvider, SqliteKeyProviderBackend
from security.secret_contract import SecretRef
from security.secret_vault import SqliteSecretVault
from security.secret_vault_sqlite import SqliteSecretVaultBackend


def test_sqlite_secret_vault_roundtrip_and_binding(tmp_path) -> None:
    key_provider = SqliteKeyProvider(SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3'))
    vault = SqliteSecretVault(SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3'), key_provider=key_provider)
    ref = SecretRef(tenant_id='tenant-a', connector_id='crm', scope='oauth', secret_name='access-token')
    stored = vault.seed_plaintext(ref=ref, plaintext='secret-1')
    assert stored.metadata['encryption_key_id'].startswith('secret-tenant-a-crm-v1')
    assert vault.get(ref) == b'secret-1'
    disabled = vault.deactivate(ref)
    assert disabled.is_active() is False
