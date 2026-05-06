from __future__ import annotations

import pytest

from security.encryption_policy import EncryptionAlgorithm, EncryptionPolicy
from security.secret_contract import SecretRef, SecretSource, SecretState
from security.secret_vault import InMemorySecretVault


def test_secret_vault_roundtrip_encrypts_and_preserves_metadata() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', connector_id='crm', scope='oauth', secret_name='access_token')

    stored = vault.seed_plaintext(
        ref=ref,
        plaintext='super-secret-token',
        source=SecretSource.CONNECTOR,
        metadata={'rotation_policy': 'daily'},
    )

    assert stored.state is SecretState.ACTIVE
    assert stored.source is SecretSource.CONNECTOR
    assert stored.metadata['rotation_policy'] == 'daily'
    assert stored.ciphertext != b'super-secret-token'
    assert vault.get(ref) == b'super-secret-token'


def test_secret_vault_rewrite_marks_rotation_and_old_plaintext_is_not_exposed() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', secret_name='api-key')

    first = vault.seed_plaintext(ref=ref, plaintext='first')
    second = vault.seed_plaintext(ref=ref, plaintext='second')

    assert first.rotated_at is None
    assert second.rotated_at is not None
    assert vault.get(ref) == b'second'
    assert second.ciphertext != first.ciphertext


def test_secret_vault_is_tenant_bound_and_tamper_fail_closed() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', secret_name='billing-webhook-secret')
    stored = vault.seed_plaintext(ref=ref, plaintext='payload-signing-secret')

    wrong_ref = SecretRef(tenant_id='tenant-b', secret_name='billing-webhook-secret')
    with pytest.raises(KeyError):
        vault.get(wrong_ref)

    tampered = stored.ciphertext[:-1] + bytes([stored.ciphertext[-1] ^ 0x01])
    vault._records[ref.key()] = stored.__class__(  # white-box corruption probe
        ref=stored.ref,
        ciphertext=tampered,
        source=stored.source,
        created_at=stored.created_at,
        updated_at=stored.updated_at,
        rotated_at=stored.rotated_at,
        deleted_at=stored.deleted_at,
        expires_at=stored.expires_at,
        state=stored.state,
        metadata=stored.metadata,
    )
    with pytest.raises(RuntimeError, match='integrity'):
        vault.get(ref)


def test_secret_vault_deactivate_blocks_plaintext_reads() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', secret_name='refresh-token')
    vault.seed_plaintext(ref=ref, plaintext='refresh-token-value')

    disabled = vault.deactivate(ref)

    assert disabled.state is SecretState.DISABLED
    with pytest.raises(RuntimeError, match='not active'):
        vault.get(ref)


def test_secret_vault_ref_binding_prevents_connector_scope_confusion() -> None:
    vault = InMemorySecretVault()
    scoped = SecretRef(tenant_id='tenant-a', connector_id='crm', scope='oauth', secret_name='token')
    vault.seed_plaintext(ref=scoped, plaintext='crm-oauth-token')

    with pytest.raises(KeyError):
        vault.get(SecretRef(tenant_id='tenant-a', connector_id='billing', scope='oauth', secret_name='token'))
    with pytest.raises(KeyError):
        vault.get(SecretRef(tenant_id='tenant-a', connector_id='crm', scope='webhook', secret_name='token'))


def test_secret_vault_refuses_fake_external_crypto_modes() -> None:
    vault = InMemorySecretVault(policy=EncryptionPolicy(algorithm=EncryptionAlgorithm.AES256_GCM))
    ref = SecretRef(tenant_id='tenant-a', secret_name='kms-bound-secret')

    with pytest.raises(NotImplementedError, match='external crypto adapter'):
        vault.seed_plaintext(ref=ref, plaintext='not-pretending-to-do-aes')


from security.secret_vault import FileSecretVault, build_default_secret_vault


def test_file_secret_vault_roundtrip_persists_across_instances(tmp_path) -> None:
    from security.secret_contract import SecretRef
    ref = SecretRef(tenant_id='tenant-a', secret_name='token', connector_id='crm')
    first = FileSecretVault(root_dir=tmp_path / 'vault')
    first.seed_plaintext(ref=ref, plaintext='secret-1')
    second = FileSecretVault(root_dir=tmp_path / 'vault')
    assert second.get(ref) == b'secret-1'


def test_build_default_secret_vault_can_select_file_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SECRET_VAULT_BACKEND', 'file')
    vault = build_default_secret_vault(root_dir=tmp_path / 'vault')
    assert isinstance(vault, FileSecretVault)



def test_secret_vault_delete_alias_disables_secret() -> None:
    ref = SecretRef(tenant_id='tenant-a', secret_name='alias-delete')
    vault = InMemorySecretVault()
    vault.seed_plaintext(ref=ref, plaintext='secret')
    record = vault.delete(ref)
    assert record.is_active() is False
