from __future__ import annotations

from pathlib import Path

from security import secret_vault as _canonical
from security.encryption_policy import EncryptionPolicy
from security.key_provider import InMemoryKeyProvider, KeyProvider
from security.secret_contract import (
    SecretRecord,
    SecretRef,
    SecretSource,
    SecretState,
    utc_now,
)


serialize_secret_record = _canonical._serialize_secret_record
deserialize_secret_record = _canonical._deserialize_secret_record
serialize_key_record = _canonical._serialize_key_record
deserialize_key_record = _canonical._deserialize_key_record
_parse_datetime = _canonical._parse_datetime


class InMemorySecretVaultMixin:
    """Compatibility mixin backed by the one canonical in-memory vault."""

    _SEALED_BOX_MAGIC = _canonical.InMemorySecretVault._SEALED_BOX_MAGIC

    __init__ = _canonical.InMemorySecretVault.__init__
    list_records = _canonical.InMemorySecretVault.list_records
    put = _canonical.InMemorySecretVault.put
    get = _canonical.InMemorySecretVault.get
    get_record = _canonical.InMemorySecretVault.get_record
    deactivate = _canonical.InMemorySecretVault.deactivate
    delete = _canonical.InMemorySecretVault.delete
    seed_plaintext = _canonical.InMemorySecretVault.seed_plaintext
    _encryption_key_id_for_record = (
        _canonical.InMemorySecretVault._encryption_key_id_for_record
    )
    _encrypt = _canonical.InMemorySecretVault._encrypt
    _decrypt = _canonical.InMemorySecretVault._decrypt
    _derive_key = _canonical.InMemorySecretVault.__dict__["_derive_key"]
    _expand_keystream = _canonical.InMemorySecretVault.__dict__["_expand_keystream"]
    _xor = _canonical.InMemorySecretVault.__dict__["_xor"]

    def _get_or_issue_key(self, ref: SecretRef):
        resolver = getattr(self, "_resolve_encryption_key", None)
        if callable(resolver):
            return resolver(ref)
        return _canonical.InMemorySecretVault._get_or_issue_key(self, ref)


class FileSecretVaultMixin(InMemorySecretVaultMixin):
    """Compatibility file mixin using canonical persistence operations."""

    def __init__(
        self,
        *,
        root_dir: str | Path,
        policy: EncryptionPolicy | None = None,
        key_provider: KeyProvider | None = None,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(policy=policy, key_provider=key_provider)
        self._load_records()

    def put(
        self,
        record: SecretRecord,
        *,
        plaintext: bytes,
    ) -> SecretRecord:
        stored = super().put(record, plaintext=plaintext)
        self._flush()
        return stored

    def deactivate(self, ref: SecretRef) -> SecretRecord:
        stored = super().deactivate(ref)
        self._flush()
        return stored

    delete = _canonical.FileSecretVault.delete
    _store_path = _canonical.FileSecretVault._store_path
    _flush = _canonical.FileSecretVault._flush
    _load_records = _canonical.FileSecretVault._load_records


__all__ = [
    "EncryptionPolicy",
    "FileSecretVaultMixin",
    "InMemoryKeyProvider",
    "InMemorySecretVaultMixin",
    "KeyProvider",
    "SecretRecord",
    "SecretRef",
    "SecretSource",
    "SecretState",
    "deserialize_key_record",
    "deserialize_secret_record",
    "serialize_key_record",
    "serialize_secret_record",
    "utc_now",
]
