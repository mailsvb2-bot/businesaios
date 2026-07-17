from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from security.encryption_policy import EncryptionAlgorithm, EncryptionPolicy
from security.key_management_contract import KeyPurpose
from security.key_provider import (
    InMemoryKeyProvider,
    KeyProvider,
    build_default_key_provider,
    describe_key_provider_backend,
    key_provider_sqlite_path,
)
from security.secret_contract import (
    SecretRecord,
    SecretRef,
    SecretSource,
    SecretState,
    utc_now,
)
from security.secret_vault_backend import SecretEnvelope


CANON_SECRET_VAULT = True


def _security_data_dir() -> Path:
    data_dir = (
        os.getenv("BUSINESAIOS_DATA_DIR", os.getenv("DATA_DIR", "data")).strip()
        or "data"
    )
    root = Path(data_dir) / "security"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _key_provider_for_ref(key_provider: KeyProvider, ref: SecretRef):
    try:
        return key_provider.get_active_for(
            purpose=KeyPurpose.SECRET_ENCRYPTION,
            tenant_id=ref.tenant_id,
            connector_id=ref.connector_id,
        )
    except KeyError:
        suffix = ref.connector_id or "global"
        return key_provider.issue_key(
            key_id=f"secret-{ref.tenant_id}-{suffix}-v1",
            purpose=KeyPurpose.SECRET_ENCRYPTION,
            tenant_id=ref.tenant_id,
            connector_id=ref.connector_id,
        )


def _derive_secret_key(master_key: bytes, label: bytes) -> bytes:
    return hashlib.sha256(label + b":" + master_key).digest()


def _expand_secret_keystream(
    derived_key: bytes,
    nonce: bytes,
    size: int,
) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(
            hashlib.sha256(
                derived_key + nonce + counter.to_bytes(8, "big")
            ).digest()
        )
        counter += 1
    return bytes(out[:size])


def _xor_payload(payload: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("key must not be empty")
    return bytes(
        byte ^ key[index % len(key)]
        for index, byte in enumerate(payload)
    )


def encrypt_secret_payload(
    *,
    plaintext: bytes,
    ref: SecretRef,
    encryption_key_id: str,
    key_provider: KeyProvider,
    policy: EncryptionPolicy,
    sealed_box_magic: bytes,
) -> bytes:
    policy.validate()
    policy.validate_plaintext_size(bytes(plaintext))
    if policy.require_external_crypto_adapter():
        raise NotImplementedError(
            f"algorithm {policy.algorithm.value} requires an external crypto "
            "adapter; the stdlib patch intentionally refuses to fake AES/Fernet"
        )
    key = key_provider.get(encryption_key_id)
    if policy.algorithm is EncryptionAlgorithm.XOR_DEMO_ONLY:
        return _xor_payload(plaintext, key.secret_bytes)
    if policy.algorithm is EncryptionAlgorithm.SEALED_BOX_V1:
        nonce = secrets.token_bytes(16)
        aad = hashlib.sha256(
            f"{ref.key()}|{encryption_key_id}".encode("utf-8")
        ).digest()
        keystream = _expand_secret_keystream(
            _derive_secret_key(key.secret_bytes, b"enc"),
            nonce,
            len(plaintext),
        )
        ciphertext = _xor_payload(plaintext, keystream)
        mac = hmac.new(
            _derive_secret_key(key.secret_bytes, b"mac"),
            aad + nonce + ciphertext,
            hashlib.sha256,
        ).digest()
        return sealed_box_magic + nonce + mac + ciphertext
    raise ValueError(
        f"unsupported encryption algorithm: {policy.algorithm.value}"
    )


def decrypt_secret_payload(
    *,
    ciphertext: bytes,
    ref: SecretRef,
    encryption_key_id: str,
    key_provider: KeyProvider,
    policy: EncryptionPolicy,
    sealed_box_magic: bytes,
) -> bytes:
    policy.validate()
    key = key_provider.get(encryption_key_id)
    if policy.algorithm is EncryptionAlgorithm.XOR_DEMO_ONLY:
        return _xor_payload(ciphertext, key.secret_bytes)
    if policy.algorithm is EncryptionAlgorithm.SEALED_BOX_V1:
        if not bytes(ciphertext).startswith(sealed_box_magic):
            raise RuntimeError("invalid sealed-box header")
        payload = bytes(ciphertext)[len(sealed_box_magic) :]
        if len(payload) < 48:
            raise RuntimeError("invalid sealed-box length")
        nonce = payload[:16]
        mac = payload[16:48]
        body = payload[48:]
        aad = hashlib.sha256(
            f"{ref.key()}|{encryption_key_id}".encode("utf-8")
        ).digest()
        expected_mac = hmac.new(
            _derive_secret_key(key.secret_bytes, b"mac"),
            aad + nonce + body,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise RuntimeError("secret ciphertext integrity check failed")
        keystream = _expand_secret_keystream(
            _derive_secret_key(key.secret_bytes, b"enc"),
            nonce,
            len(body),
        )
        return _xor_payload(body, keystream)
    if policy.require_external_crypto_adapter():
        raise NotImplementedError(
            f"algorithm {policy.algorithm.value} requires an external crypto "
            "adapter; the stdlib patch intentionally refuses to fake AES/Fernet"
        )
    raise ValueError(
        f"unsupported encryption algorithm: {policy.algorithm.value}"
    )


def _serialize_secret_record(record: SecretRecord) -> dict[str, object]:
    return {
        "ref": {
            "tenant_id": record.ref.tenant_id,
            "secret_name": record.ref.secret_name,
            "version": record.ref.version,
            "connector_id": record.ref.connector_id,
            "scope": record.ref.scope,
        },
        "ciphertext_b64": base64.b64encode(
            bytes(record.ciphertext)
        ).decode("ascii"),
        "source": record.source.value,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "rotated_at": (
            None
            if record.rotated_at is None
            else record.rotated_at.isoformat()
        ),
        "deleted_at": (
            None
            if record.deleted_at is None
            else record.deleted_at.isoformat()
        ),
        "expires_at": (
            None
            if record.expires_at is None
            else record.expires_at.isoformat()
        ),
        "state": record.state.value,
        "metadata": dict(record.metadata or {}),
    }


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _deserialize_secret_record(payload: dict[str, object]) -> SecretRecord:
    ref_payload = dict(payload.get("ref") or {})
    return SecretRecord(
        ref=SecretRef(
            tenant_id=str(ref_payload.get("tenant_id") or ""),
            secret_name=str(ref_payload.get("secret_name") or ""),
            version=str(ref_payload.get("version") or "current"),
            connector_id=(
                None
                if ref_payload.get("connector_id") in {None, ""}
                else str(ref_payload.get("connector_id"))
            ),
            scope=(
                None
                if ref_payload.get("scope") in {None, ""}
                else str(ref_payload.get("scope"))
            ),
        ),
        ciphertext=base64.b64decode(
            str(payload.get("ciphertext_b64") or "")
        ),
        source=SecretSource(
            str(payload.get("source") or SecretSource.UNKNOWN.value)
        ),
        created_at=_parse_datetime(payload.get("created_at")) or utc_now(),
        updated_at=_parse_datetime(payload.get("updated_at")) or utc_now(),
        rotated_at=_parse_datetime(payload.get("rotated_at")),
        deleted_at=_parse_datetime(payload.get("deleted_at")),
        expires_at=_parse_datetime(payload.get("expires_at")),
        state=SecretState(
            str(payload.get("state") or SecretState.ACTIVE.value)
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def _serialize_key_record(record) -> dict[str, object]:
    from security.key_provider import _serialize_record

    return _serialize_record(record)


def _deserialize_key_record(payload: dict[str, object]):
    from security.key_provider import _deserialize_record

    return _deserialize_record(payload)


class SecretVault(ABC):
    @abstractmethod
    def put(
        self,
        record: SecretRecord,
        *,
        plaintext: bytes,
    ) -> SecretRecord:
        raise NotImplementedError

    @abstractmethod
    def get(self, ref: SecretRef) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def get_record(self, ref: SecretRef) -> SecretRecord:
        raise NotImplementedError

    @abstractmethod
    def deactivate(self, ref: SecretRef) -> SecretRecord:
        raise NotImplementedError

    def delete(self, ref: SecretRef) -> SecretRecord:
        return self.deactivate(ref)


class InMemorySecretVault(SecretVault):
    _SEALED_BOX_MAGIC = b"SB1:"

    def __init__(
        self,
        *,
        policy: EncryptionPolicy | None = None,
        key_provider: KeyProvider | None = None,
    ) -> None:
        self._policy = policy or EncryptionPolicy()
        self._policy.validate()
        self._key_provider = key_provider or InMemoryKeyProvider()
        self._records: dict[str, SecretRecord] = {}

    def list_records(self) -> tuple[SecretRecord, ...]:
        return tuple(self._records.values())

    def put(
        self,
        record: SecretRecord,
        *,
        plaintext: bytes,
    ) -> SecretRecord:
        record.validate()
        record.ref.validate()
        self._policy.validate_plaintext_size(bytes(plaintext))
        key = self._get_or_issue_key(record.ref)
        ciphertext = self._encrypt(
            bytes(plaintext),
            ref=record.ref,
            encryption_key_id=key.key_id,
        )
        now = utc_now()
        existing = self._records.get(record.ref.key())
        prior_nonce = (
            None
            if existing is None
            else str(existing.metadata.get("version_nonce") or "").strip()
            or None
        )
        version_nonce = prior_nonce or secrets.token_hex(16)
        rotated_at = now if existing is not None else record.rotated_at
        metadata = {
            **dict(record.metadata or {}),
            "encryption_key_id": key.key_id,
            "version_nonce": version_nonce,
        }
        stored = replace(
            record,
            ciphertext=ciphertext,
            updated_at=now,
            rotated_at=rotated_at,
            state=SecretState.ACTIVE,
            metadata=metadata,
        )
        stored.validate()
        self._records[record.ref.key()] = stored
        return stored

    def get(self, ref: SecretRef) -> bytes:
        record = self.get_record(ref)
        if not record.is_active():
            raise RuntimeError(f"secret {ref.key()} is not active")
        return self._decrypt(
            record.ciphertext,
            ref=ref,
            encryption_key_id=self._encryption_key_id_for_record(
                record,
                ref=ref,
            ),
        )

    def get_record(self, ref: SecretRef) -> SecretRecord:
        ref.validate()
        record = self._records.get(ref.key())
        if record is None:
            raise KeyError(f"unknown secret ref: {ref.key()}")
        return record

    def deactivate(self, ref: SecretRef) -> SecretRecord:
        current = self.get_record(ref)
        updated = current.disable(now=utc_now())
        self._records[ref.key()] = updated
        return updated

    def delete(self, ref: SecretRef) -> SecretRecord:
        return self.deactivate(ref)

    def seed_plaintext(
        self,
        *,
        ref: SecretRef,
        plaintext: str | bytes,
        source: SecretSource = SecretSource.MEMORY,
        metadata: dict[str, str] | None = None,
    ) -> SecretRecord:
        data = (
            plaintext.encode("utf-8")
            if isinstance(plaintext, str)
            else bytes(plaintext)
        )
        placeholder = SecretRecord(
            ref=ref,
            ciphertext=b"pending",
            source=source,
            metadata=dict(metadata or {}),
        )
        return self.put(placeholder, plaintext=data)

    def _encryption_key_id_for_record(
        self,
        record: SecretRecord,
        *,
        ref: SecretRef,
    ) -> str:
        key_id = str(
            record.metadata.get("encryption_key_id") or ""
        ).strip()
        if key_id:
            return key_id
        return self._get_or_issue_key(ref).key_id

    def _encrypt(
        self,
        plaintext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        return encrypt_secret_payload(
            plaintext=plaintext,
            ref=ref,
            encryption_key_id=encryption_key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._SEALED_BOX_MAGIC,
        )

    def _decrypt(
        self,
        ciphertext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        return decrypt_secret_payload(
            ciphertext=ciphertext,
            ref=ref,
            encryption_key_id=encryption_key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._SEALED_BOX_MAGIC,
        )

    def _get_or_issue_key(self, ref: SecretRef):
        return _key_provider_for_ref(self._key_provider, ref)

    @staticmethod
    def _derive_key(master_key: bytes, label: bytes) -> bytes:
        return _derive_secret_key(master_key, label)

    @classmethod
    def _expand_keystream(
        cls,
        derived_key: bytes,
        nonce: bytes,
        size: int,
    ) -> bytes:
        del cls
        return _expand_secret_keystream(derived_key, nonce, size)

    @staticmethod
    def _xor(payload: bytes, key: bytes) -> bytes:
        return _xor_payload(payload, key)


class FileSecretVault(InMemorySecretVault):
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

    def delete(self, ref: SecretRef) -> SecretRecord:
        return self.deactivate(ref)

    def _store_path(self) -> Path:
        return self._root_dir / "secret_vault.json"

    def _flush(self) -> None:
        path = self._store_path()
        tmp = path.with_suffix(".json.tmp")
        key_records = getattr(self._key_provider, "_records", {})
        payload = {
            "records": [
                _serialize_secret_record(record)
                for record in self.list_records()
            ],
            "keys": [
                _serialize_key_record(record)
                for record in key_records.values()
            ],
        }
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _load_records(self) -> None:
        path = self._store_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(payload, list):
            records_payload = payload
            keys_payload = []
        elif isinstance(payload, dict):
            records_payload = list(payload.get("records") or [])
            keys_payload = list(payload.get("keys") or [])
        else:
            return
        for item in keys_payload:
            if not isinstance(item, dict):
                continue
            try:
                self._key_provider.register(_deserialize_key_record(item))
            except Exception:
                continue
        for item in records_payload:
            if not isinstance(item, dict):
                continue
            try:
                record = _deserialize_secret_record(item)
            except Exception:
                continue
            self._records[record.ref.key()] = record


class SqliteSecretVault(SecretVault):
    _SEALED_BOX_MAGIC = InMemorySecretVault._SEALED_BOX_MAGIC

    def __init__(
        self,
        backend,
        *,
        policy: EncryptionPolicy | None = None,
        key_provider: KeyProvider | None = None,
    ) -> None:
        self._backend = backend
        self._policy = policy or EncryptionPolicy()
        self._policy.validate()
        self._key_provider = key_provider or build_default_key_provider()

    def put(
        self,
        record: SecretRecord,
        *,
        plaintext: bytes,
    ) -> SecretRecord:
        record.validate()
        self._policy.validate_plaintext_size(bytes(plaintext))
        try:
            existing = self._backend.get(record.ref)
        except KeyError:
            existing = None
        key = self._resolve_encryption_key(record.ref)
        version_nonce = (
            existing.version_nonce
            if existing is not None
            else secrets.token_hex(16)
        )
        ciphertext = self._encrypt(
            bytes(plaintext),
            ref=record.ref,
            encryption_key_id=key.key_id,
        )
        now = utc_now()
        stored_record = replace(
            record,
            ciphertext=ciphertext,
            updated_at=now,
            rotated_at=now if existing is not None else record.rotated_at,
            state=SecretState.ACTIVE,
            metadata={
                **dict(record.metadata or {}),
                "encryption_key_id": key.key_id,
                "version_nonce": version_nonce,
            },
        )
        envelope = SecretEnvelope(
            record=stored_record,
            encryption_key_id=key.key_id,
            version_nonce=version_nonce,
            row_version=(
                1 if existing is None else existing.row_version
            ),
            etag=None if existing is None else existing.etag,
            metadata=(
                {} if existing is None else dict(existing.metadata or {})
            ),
        )
        persisted = self._backend.put(
            envelope,
            expected_row_version=(
                0 if existing is None else existing.row_version
            ),
        )
        return persisted.record

    def get(self, ref: SecretRef) -> bytes:
        envelope = self._backend.get(ref)
        if not envelope.record.is_active():
            raise RuntimeError(f"secret {ref.key()} is not active")
        return self._decrypt(
            envelope.record.ciphertext,
            ref=ref,
            encryption_key_id=envelope.encryption_key_id,
        )

    def get_record(self, ref: SecretRef) -> SecretRecord:
        return self._backend.get(ref).record

    def deactivate(self, ref: SecretRef) -> SecretRecord:
        return self._backend.deactivate(ref).record

    def delete(self, ref: SecretRef) -> SecretRecord:
        return self._backend.soft_delete(ref).record

    def seed_plaintext(
        self,
        *,
        ref: SecretRef,
        plaintext: str | bytes,
        source: SecretSource = SecretSource.MEMORY,
        metadata: dict[str, str] | None = None,
    ) -> SecretRecord:
        data = (
            plaintext.encode("utf-8")
            if isinstance(plaintext, str)
            else bytes(plaintext)
        )
        placeholder = SecretRecord(
            ref=ref,
            ciphertext=b"pending",
            source=source,
            metadata=dict(metadata or {}),
        )
        return self.put(placeholder, plaintext=data)

    def _resolve_encryption_key(self, ref: SecretRef):
        return _key_provider_for_ref(self._key_provider, ref)

    def _encrypt(
        self,
        plaintext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        return encrypt_secret_payload(
            plaintext=plaintext,
            ref=ref,
            encryption_key_id=encryption_key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._SEALED_BOX_MAGIC,
        )

    def _decrypt(
        self,
        ciphertext: bytes,
        *,
        ref: SecretRef,
        encryption_key_id: str,
    ) -> bytes:
        return decrypt_secret_payload(
            ciphertext=ciphertext,
            ref=ref,
            encryption_key_id=encryption_key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._SEALED_BOX_MAGIC,
        )


def secret_vault_sqlite_path() -> Path:
    explicit = os.getenv(
        "BUSINESAIOS_SECRET_VAULT_SQLITE_PATH",
        "",
    ).strip()
    if explicit:
        return Path(explicit)
    return _security_data_dir() / "secret_vault.sqlite3"


def build_default_secret_vault(
    *,
    root_dir: str | Path | None = None,
    policy: EncryptionPolicy | None = None,
    key_provider: KeyProvider | None = None,
) -> SecretVault:
    storage = os.getenv(
        "BUSINESAIOS_SECRET_VAULT_BACKEND",
        "file",
    ).strip().lower()
    resolved_key_provider = key_provider
    if storage in {"memory", "inmemory"}:
        return InMemorySecretVault(
            policy=policy,
            key_provider=(
                resolved_key_provider or build_default_key_provider()
            ),
        )
    if storage == "sqlite":
        from security.key_provider_sqlite import (
            SqliteKeyProvider,
            SqliteKeyProviderBackend,
        )
        from security.secret_vault_sqlite import SqliteSecretVaultBackend

        if resolved_key_provider is None:
            key_mode = describe_key_provider_backend()
            if key_mode == "sqlite":
                resolved_key_provider = SqliteKeyProvider(
                    SqliteKeyProviderBackend(key_provider_sqlite_path())
                )
            else:
                resolved_key_provider = build_default_key_provider()
        return SqliteSecretVault(
            SqliteSecretVaultBackend(secret_vault_sqlite_path()),
            policy=policy,
            key_provider=resolved_key_provider,
        )
    resolved_key_provider = (
        resolved_key_provider or build_default_key_provider()
    )
    vault_root = (
        Path(root_dir) if root_dir is not None else _security_data_dir()
    )
    return FileSecretVault(
        root_dir=vault_root,
        policy=policy,
        key_provider=resolved_key_provider,
    )


__all__ = [
    "CANON_SECRET_VAULT",
    "build_default_secret_vault",
    "decrypt_secret_payload",
    "encrypt_secret_payload",
    "FileSecretVault",
    "InMemorySecretVault",
    "SecretVault",
    "SqliteSecretVault",
    "secret_vault_sqlite_path",
]
