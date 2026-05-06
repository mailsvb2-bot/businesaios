from __future__ import annotations

from security.key_management_contract import KeyPurpose, KeyStatus
from security.key_provider_sqlite import SqliteKeyProvider, SqliteKeyProviderBackend


def test_sqlite_key_provider_roundtrip_and_rotate(tmp_path) -> None:
    provider = SqliteKeyProvider(SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3'))
    first = provider.issue_key(key_id='secret-tenant-a-global-v1', purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='tenant-a')
    active = provider.get_active_for(purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='tenant-a')
    assert active.key_id == first.key_id
    rotated = provider.rotate(current_key_id=first.key_id, new_key_id='secret-tenant-a-global-v2')
    assert rotated.key_id == 'secret-tenant-a-global-v2'
    assert provider.get(first.key_id).status is KeyStatus.DEPRECATED
    assert provider.get_active_for(purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='tenant-a').key_id == rotated.key_id
