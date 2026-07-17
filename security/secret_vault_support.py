from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from security.encryption_policy import EncryptionPolicy
from security.key_provider import InMemoryKeyProvider, KeyProvider
from security.secret_contract import (
    SecretRecord,
    SecretRef,
    SecretSource,
    SecretState,
)


def serialize_secret_record(record: SecretRecord) -> dict[str, object]:
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


def deserialize_secret_record(payload: dict[str, object]) -> SecretRecord:
    ref_payload = dict(payload.get("ref") or {})
    now = datetime.now().astimezone()
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
        created_at=_parse_datetime(payload.get("created_at")) or now,
        updated_at=_parse_datetime(payload.get("updated_at")) or now,
        rotated_at=_parse_datetime(payload.get("rotated_at")),
        deleted_at=_parse_datetime(payload.get("deleted_at")),
        expires_at=_parse_datetime(payload.get("expires_at")),
        state=SecretState(
            str(payload.get("state") or SecretState.ACTIVE.value)
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def serialize_key_record(record) -> dict[str, object]:
    from security.key_provider import _serialize_record

    return _serialize_record(record)


def deserialize_key_record(payload: dict[str, object]):
    from security.key_provider import _deserialize_record

    return _deserialize_record(payload)


class InMemorySecretVaultMixin:
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
        now = datetime.now().astimezone()
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
        updated = current.disable(now=datetime.now().astimezone())
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

    def _get_or_issue_key(self, ref: SecretRef):
        return self._resolve_encryption_key(ref)


class FileSecretVaultMixin(InMemorySecretVaultMixin):
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
                serialize_secret_record(record)
                for record in self.list_records()
            ],
            "keys": [
                serialize_key_record(record)
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
                self._key_provider.register(deserialize_key_record(item))
            except Exception:
                continue
        for item in records_payload:
            if not isinstance(item, dict):
                continue
            try:
                record = deserialize_secret_record(item)
            except Exception:
                continue
            self._records[record.ref.key()] = record
