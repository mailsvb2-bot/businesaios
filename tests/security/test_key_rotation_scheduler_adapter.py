from __future__ import annotations

from datetime import timedelta

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, utc_now
from security.key_provider_sqlite import SqliteKeyProvider, SqliteKeyProviderBackend
from security.key_rotation_scheduler import (
    KeyRotationScheduler,
    KeyRotationSchedulerConfig,
    StdlibSecretReencryptionAdapter,
)
from security.secret_contract import SecretRef
from security.secret_vault import SqliteSecretVault
from security.secret_vault_sqlite import SqliteSecretVaultBackend


def test_key_rotation_scheduler_reencrypts_bound_secrets_with_stdlib_adapter(tmp_path) -> None:
    key_backend = SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3')
    key_provider = SqliteKeyProvider(key_backend)
    secret_backend = SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3')
    vault = SqliteSecretVault(secret_backend, key_provider=key_provider)

    old_key = KeyMaterialRecord(
        key_id='secret-tenant-a-global-v1',
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        secret_bytes=b'1' * 32,
        tenant_id='tenant-a',
        created_at=utc_now() - timedelta(days=120),
        activated_at=utc_now() - timedelta(days=120),
    )
    key_backend.upsert(old_key)
    ref = SecretRef(tenant_id='tenant-a', secret_name='billing-token')
    vault.seed_plaintext(ref=ref, plaintext='super-secret')
    before = secret_backend.get(ref)
    assert before.encryption_key_id == old_key.key_id

    scheduler = KeyRotationScheduler(
        key_backend=key_backend,
        secret_backend=secret_backend,
        secret_reencryption_adapter=StdlibSecretReencryptionAdapter(key_provider=key_provider),
        config=KeyRotationSchedulerConfig(key_max_age_days=90),
    )

    result = scheduler.execute()
    assert result[0].status == 'rotated'
    after = secret_backend.get(ref)
    assert after.encryption_key_id == result[0].rotated_key_id
    assert after.record.ciphertext != before.record.ciphertext
    assert vault.get(ref) == b'super-secret'


def test_key_rotation_scheduler_registers_new_key_before_secret_rekey(tmp_path) -> None:
    key_backend = SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3')
    key_provider = SqliteKeyProvider(key_backend)
    secret_backend = SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3')
    vault = SqliteSecretVault(secret_backend, key_provider=key_provider)

    old_key = KeyMaterialRecord(
        key_id='secret-tenant-a-global-v1',
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        secret_bytes=b'2' * 32,
        tenant_id='tenant-a',
        created_at=utc_now() - timedelta(days=120),
        activated_at=utc_now() - timedelta(days=120),
    )
    key_backend.upsert(old_key)
    ref = SecretRef(tenant_id='tenant-a', secret_name='api-token')
    vault.seed_plaintext(ref=ref, plaintext='super-secret')

    seen_new_key_ids: list[str] = []

    class _AssertingAdapter(StdlibSecretReencryptionAdapter):
        def reencrypt_envelope(self, *, envelope, old_encryption_key_id, new_key):
            persisted = key_backend.get(new_key.key_id)
            seen_new_key_ids.append(persisted.key_id)
            return super().reencrypt_envelope(
                envelope=envelope,
                old_encryption_key_id=old_encryption_key_id,
                new_key=new_key,
            )

    scheduler = KeyRotationScheduler(
        key_backend=key_backend,
        secret_backend=secret_backend,
        secret_reencryption_adapter=_AssertingAdapter(key_provider=key_provider),
        config=KeyRotationSchedulerConfig(key_max_age_days=90),
    )

    result = scheduler.execute()
    assert result[0].status == 'rotated'
    assert seen_new_key_ids == [result[0].rotated_key_id]


def test_reencrypt_adapter_rejects_key_binding_mismatch(tmp_path) -> None:
    key_backend = SqliteKeyProviderBackend(tmp_path / 'keys.sqlite3')
    key_provider = SqliteKeyProvider(key_backend)
    secret_backend = SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3')
    vault = SqliteSecretVault(secret_backend, key_provider=key_provider)

    old_key = KeyMaterialRecord(
        key_id='secret-tenant-a-global-v1',
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        secret_bytes=b'3' * 32,
        tenant_id='tenant-a',
        created_at=utc_now() - timedelta(days=120),
        activated_at=utc_now() - timedelta(days=120),
    )
    key_backend.upsert(old_key)
    ref = SecretRef(tenant_id='tenant-a', secret_name='ops-token')
    vault.seed_plaintext(ref=ref, plaintext='super-secret')
    envelope = secret_backend.get(ref)
    adapter = StdlibSecretReencryptionAdapter(key_provider=key_provider)

    import pytest
    with pytest.raises(RuntimeError, match='key binding mismatch'):
        adapter.reencrypt_envelope(
            envelope=envelope,
            old_encryption_key_id='wrong-key-id',
            new_key=old_key,
        )
