from __future__ import annotations

from pathlib import Path

import pytest

from security import secret_vault as canonical
from security import secret_vault_support as support
from security.secret_contract import SecretRecord, SecretRef, SecretSource, SecretState


class MemoryVault(support.InMemorySecretVaultMixin):
    pass


class HookVault(support.InMemorySecretVaultMixin):
    def __init__(self) -> None:
        self.resolve_calls: list[SecretRef] = []
        super().__init__()

    def _resolve_encryption_key(self, ref: SecretRef):
        self.resolve_calls.append(ref)
        return canonical._key_provider_for_ref(self._key_provider, ref)


class LegacyCryptoBase:
    def _resolve_encryption_key(self, ref: SecretRef):
        return canonical._key_provider_for_ref(self._key_provider, ref)

    def _encrypt(
        self,
        plaintext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        del ref, encryption_key_id
        self.crypto_calls = [*getattr(self, "crypto_calls", []), "encrypt"]
        return b"legacy:" + plaintext

    def _decrypt(
        self,
        ciphertext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        del ref, encryption_key_id
        self.crypto_calls = [*getattr(self, "crypto_calls", []), "decrypt"]
        return ciphertext.removeprefix(b"legacy:")


class MultiBaseVault(support.InMemorySecretVaultMixin, LegacyCryptoBase):
    pass


class FileVault(support.FileSecretVaultMixin):
    pass


def _record(ref: SecretRef, *, source: SecretSource = SecretSource.MEMORY) -> SecretRecord:
    return SecretRecord(ref=ref, ciphertext=b"pending", source=source)


def test_support_functions_and_methods_delegate_to_canonical_owner() -> None:
    assert support.serialize_secret_record is canonical._serialize_secret_record
    assert support.deserialize_secret_record is canonical._deserialize_secret_record
    assert support.serialize_key_record is canonical._serialize_key_record
    assert support.deserialize_key_record is canonical._deserialize_key_record
    assert support._parse_datetime is canonical._parse_datetime

    assert support.InMemorySecretVaultMixin.put is canonical.InMemorySecretVault.put
    assert support.InMemorySecretVaultMixin.get is canonical.InMemorySecretVault.get
    assert support.FileSecretVaultMixin._flush is canonical.FileSecretVault._flush
    assert (
        support.FileSecretVaultMixin._load_records
        is canonical.FileSecretVault._load_records
    )


def test_memory_mixin_uses_canonical_crypto_and_lifecycle() -> None:
    vault = MemoryVault()
    ref = SecretRef("tenant-a", "api-key", connector_id="telegram")

    stored = vault.put(_record(ref), plaintext=b"top-secret")

    assert stored.ciphertext != b"top-secret"
    assert stored.metadata["encryption_key_id"]
    assert stored.metadata["version_nonce"]
    assert vault.get(ref) == b"top-secret"
    assert vault.list_records() == (stored,)

    disabled = vault.deactivate(ref)
    assert disabled.state is SecretState.DISABLED
    with pytest.raises(RuntimeError, match="not active"):
        vault.get(ref)


def test_legacy_resolve_encryption_key_hook_remains_supported() -> None:
    vault = HookVault()
    ref = SecretRef("tenant-a", "legacy-hook")

    stored = vault.seed_plaintext(ref=ref, plaintext="secret")

    assert vault.resolve_calls == [ref]
    assert vault.get(ref) == b"secret"
    assert stored.metadata["encryption_key_id"]


def test_multi_base_legacy_crypto_hooks_are_not_shadowed() -> None:
    vault = MultiBaseVault()
    ref = SecretRef("tenant-a", "multi-base")

    stored = vault.put(_record(ref), plaintext=b"secret")

    assert stored.ciphertext == b"legacy:secret"
    assert vault.get(ref) == b"secret"
    assert vault.crypto_calls == ["encrypt", "decrypt"]


def test_file_mixin_persists_keys_records_and_deactivation(tmp_path: Path) -> None:
    ref = SecretRef("tenant-a", "persistent-key", scope="payments")
    vault = FileVault(root_dir=tmp_path)
    stored = vault.put(
        _record(ref, source=SecretSource.FILE),
        plaintext=b"persisted-secret",
    )

    store_path = tmp_path / "secret_vault.json"
    assert store_path.exists()
    assert FileVault(root_dir=tmp_path).get(ref) == b"persisted-secret"

    disabled = vault.deactivate(ref)
    assert disabled.state is SecretState.DISABLED
    reloaded = FileVault(root_dir=tmp_path)
    assert reloaded.get_record(ref).state is SecretState.DISABLED
    with pytest.raises(RuntimeError, match="not active"):
        reloaded.get(ref)

    assert stored.ref == ref


def test_file_delete_and_serialization_round_trips(tmp_path: Path) -> None:
    ref = SecretRef("tenant-a", "round-trip", version="v2")
    vault = FileVault(root_dir=tmp_path)
    stored = vault.put(_record(ref), plaintext=b"round-trip-secret")
    key = vault._key_provider.get(stored.metadata["encryption_key_id"])

    assert support.deserialize_secret_record(
        support.serialize_secret_record(stored)
    ) == stored
    assert support.deserialize_key_record(support.serialize_key_record(key)) == key

    deleted = vault.delete(ref)
    assert deleted.state is SecretState.DISABLED
    assert FileVault(root_dir=tmp_path).get_record(ref).state is SecretState.DISABLED
