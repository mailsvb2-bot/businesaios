from __future__ import annotations

from datetime import timedelta

import pytest

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, utc_now
from security.key_provider_sqlite import SqliteKeyProviderBackend
from security.key_rotation_scheduler import KeyRotationScheduler, KeyRotationSchedulerConfig
from security.secret_vault_sqlite import SqliteSecretVaultBackend


def test_key_rotation_scheduler_fails_closed_without_reencrypt_adapter(tmp_path) -> None:
    key_backend = SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3')
    old = KeyMaterialRecord(
        key_id='secret-tenant-a-global-v1',
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        secret_bytes=b'1' * 32,
        tenant_id='tenant-a',
        created_at=utc_now() - timedelta(days=120),
        activated_at=utc_now() - timedelta(days=120),
    )
    key_backend.upsert(old)
    scheduler = KeyRotationScheduler(
        key_backend=key_backend,
        secret_backend=SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3'),
        config=KeyRotationSchedulerConfig(key_max_age_days=90),
    )
    result = scheduler.execute()
    assert result[0].status == 'rotated'

    # bind a secret and require adapter
    secret_backend = SqliteSecretVaultBackend(tmp_path / 'vault2.sqlite3')
    secret_backend.seed_encrypted(
        ref=__import__('security.secret_contract', fromlist=['SecretRef']).SecretRef(tenant_id='tenant-a', secret_name='api'),
        ciphertext=b'abc',
        encryption_key_id=result[0].rotated_key_id or 'missing',
    )
    key_backend.apply_status_change(
        __import__('security.key_provider_backend', fromlist=['KeyStatusChange']).KeyStatusChange(
            key_id=result[0].rotated_key_id or 'missing',
            from_status=__import__('security.key_management_contract', fromlist=['KeyStatus']).KeyStatus.ACTIVE,
            to_status=__import__('security.key_management_contract', fromlist=['KeyStatus']).KeyStatus.ACTIVE,
            changed_at=utc_now(),
        )
    )
    scheduler2 = KeyRotationScheduler(
        key_backend=key_backend,
        secret_backend=secret_backend,
        config=KeyRotationSchedulerConfig(key_max_age_days=0 if False else 90),
    )
    with pytest.raises(RuntimeError, match='adapter'):
        scheduler2._rekey_bound_secrets(old_key=key_backend.get(result[0].rotated_key_id or 'missing'), new_key=key_backend.get(result[0].rotated_key_id or 'missing'), now=utc_now())
