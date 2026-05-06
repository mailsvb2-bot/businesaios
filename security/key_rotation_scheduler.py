from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping, Protocol

from security.encryption_policy import EncryptionPolicy
from security.key_provider import KeyProvider
from security.secret_contract import SecretRef
from security.secret_vault import decrypt_secret_payload, encrypt_secret_payload

from security.credential_rotation_policy import CredentialRotationPolicy
from security.key_management_contract import KeyMaterialRecord, KeyPurpose, utc_now
from security.key_provider_backend import KeyProviderBackend
from security.secret_vault_backend import SecretEnvelope, SecretVaultBackend


CANON_KEY_ROTATION_SCHEDULER = True


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class SecretReencryptionAdapter(Protocol):
    def reencrypt_envelope(self, *, envelope: SecretEnvelope, old_encryption_key_id: str, new_key: KeyMaterialRecord) -> bytes: ...


class StdlibSecretReencryptionAdapter:
    def __init__(
        self,
        *,
        key_provider: KeyProvider,
        policy: EncryptionPolicy | None = None,
        sealed_box_magic: bytes = b"SB1:",
    ) -> None:
        self._key_provider = key_provider
        self._policy = policy or EncryptionPolicy()
        self._policy.validate()
        self._sealed_box_magic = bytes(sealed_box_magic)

    def reencrypt_envelope(self, *, envelope: SecretEnvelope, old_encryption_key_id: str, new_key: KeyMaterialRecord) -> bytes:
        if envelope.encryption_key_id != old_encryption_key_id:
            raise RuntimeError(
                f"secret envelope key binding mismatch: expected {old_encryption_key_id}, got {envelope.encryption_key_id}"
            )
        plaintext = decrypt_secret_payload(
            ciphertext=envelope.record.ciphertext,
            ref=envelope.record.ref,
            encryption_key_id=old_encryption_key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._sealed_box_magic,
        )
        if self._policy.algorithm.value == "xor_demo_only":
            return bytes(byte ^ new_key.secret_bytes[index % len(new_key.secret_bytes)] for index, byte in enumerate(plaintext))
        if self._policy.algorithm.value == "sealed_box_v1":
            import hashlib, hmac, secrets
            nonce = secrets.token_bytes(16)
            aad = hashlib.sha256(f"{envelope.record.ref.key()}|{new_key.key_id}".encode("utf-8")).digest()
            enc_key = hashlib.sha256(b"enc:" + bytes(new_key.secret_bytes)).digest()
            mac_key = hashlib.sha256(b"mac:" + bytes(new_key.secret_bytes)).digest()
            out = bytearray()
            counter = 0
            while len(out) < len(plaintext):
                out.extend(hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest())
                counter += 1
            body = bytes(byte ^ out[index] for index, byte in enumerate(plaintext))
            mac = hmac.new(mac_key, aad + nonce + body, hashlib.sha256).digest()
            return self._sealed_box_magic + nonce + mac + body
        return encrypt_secret_payload(
            plaintext=plaintext,
            ref=envelope.record.ref,
            encryption_key_id=new_key.key_id,
            key_provider=self._key_provider,
            policy=self._policy,
            sealed_box_magic=self._sealed_box_magic,
        )


@dataclass(frozen=True)
class RotationTask:
    kind: str
    tenant_id: str | None
    connector_id: str | None
    key_id: str | None = None
    due_reason: str = "unspecified"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.kind or "").strip():
            raise ValueError("kind is required")
        if not str(self.due_reason or "").strip():
            raise ValueError("due_reason is required")


@dataclass(frozen=True)
class RotationExecution:
    task: RotationTask
    status: str
    rotated_key_id: str | None = None
    notes: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        self.task.validate()
        if not str(self.status or "").strip():
            raise ValueError("status is required")


@dataclass(frozen=True)
class KeyRotationSchedulerConfig:
    key_max_age_days: int = 90
    key_scan_limit: int = 200
    rekey_batch_limit: int = 500
    generate_key_bytes: int = 32
    require_secret_reencryption_adapter: bool = True

    def validate(self) -> None:
        if int(self.key_max_age_days) <= 0:
            raise ValueError("key_max_age_days must be > 0")
        if int(self.key_scan_limit) <= 0:
            raise ValueError("key_scan_limit must be > 0")
        if int(self.rekey_batch_limit) <= 0:
            raise ValueError("rekey_batch_limit must be > 0")
        if int(self.generate_key_bytes) < 16:
            raise ValueError("generate_key_bytes must be >= 16")


class KeyRotationScheduler:
    def __init__(
        self,
        *,
        key_backend: KeyProviderBackend,
        secret_backend: SecretVaultBackend,
        credential_rotation_policy: CredentialRotationPolicy | None = None,
        secret_reencryption_adapter: SecretReencryptionAdapter | None = None,
        config: KeyRotationSchedulerConfig | None = None,
    ) -> None:
        self._key_backend = key_backend
        self._secret_backend = secret_backend
        self._credential_rotation_policy = credential_rotation_policy or CredentialRotationPolicy()
        self._credential_rotation_policy.validate()
        self._secret_reencryption_adapter = secret_reencryption_adapter
        self._config = config or KeyRotationSchedulerConfig()
        self._config.validate()

    def plan(self, *, now: datetime | None = None) -> tuple[RotationTask, ...]:
        moment = now or utc_now()
        _require_aware(moment, field_name="now")
        tasks: list[RotationTask] = []
        due_keys = self._key_backend.list_due_for_rotation(
            max_age=timedelta(days=int(self._config.key_max_age_days)),
            now=moment,
            limit=int(self._config.key_scan_limit),
        )
        for candidate in due_keys:
            task = RotationTask(
                kind="rotate_key",
                tenant_id=candidate.record.tenant_id,
                connector_id=candidate.record.connector_id,
                key_id=candidate.record.key_id,
                due_reason=candidate.due_reason,
                metadata=dict(candidate.metadata or {}),
            )
            task.validate()
            tasks.append(task)
        return tuple(tasks)

    def execute(self, *, now: datetime | None = None) -> tuple[RotationExecution, ...]:
        moment = now or utc_now()
        _require_aware(moment, field_name="now")
        executions: list[RotationExecution] = []
        for task in self.plan(now=moment):
            if task.kind != "rotate_key":
                executions.append(RotationExecution(task=task, status="skipped", notes={"reason": "unsupported_task_kind"}))
                continue
            executions.append(self._execute_key_rotation(task=task, now=moment))
        return tuple(executions)

    def _execute_key_rotation(self, *, task: RotationTask, now: datetime) -> RotationExecution:
        if not task.key_id:
            return RotationExecution(task=task, status="failed", notes={"reason": "missing_key_id"})
        old_key = self._key_backend.get(task.key_id)
        new_key = KeyMaterialRecord(
            key_id=self._next_key_id(old_key=old_key, now=now),
            purpose=old_key.purpose,
            secret_bytes=secrets.token_bytes(int(self._config.generate_key_bytes)),
            tenant_id=old_key.tenant_id,
            connector_id=old_key.connector_id,
            metadata={**dict(old_key.metadata or {}), "rotation_parent_key_id": old_key.key_id, "rotated_at": now.isoformat()},
        )
        self._key_backend.rotate(old_key_id=old_key.key_id, new_record=new_key, rotated_at=now)
        bound_secret_count = 0
        rekeyed_secret_count = 0
        if old_key.purpose is KeyPurpose.SECRET_ENCRYPTION:
            bound_secret_count, rekeyed_secret_count = self._rekey_bound_secrets(old_key=old_key, new_key=new_key, now=now)
        return RotationExecution(
            task=task,
            status="rotated",
            rotated_key_id=new_key.key_id,
            notes={
                "old_key_id": old_key.key_id,
                "new_key_id": new_key.key_id,
                "bound_secret_count": str(bound_secret_count),
                "rekeyed_secret_count": str(rekeyed_secret_count),
            },
        )

    def _rekey_bound_secrets(self, *, old_key: KeyMaterialRecord, new_key: KeyMaterialRecord, now: datetime) -> tuple[int, int]:
        envelopes = self._secret_backend.list_by_encryption_key_id(
            encryption_key_id=old_key.key_id,
            tenant_id=old_key.tenant_id,
            connector_id=old_key.connector_id,
            limit=int(self._config.rekey_batch_limit),
        )
        if not envelopes:
            return 0, 0
        if self._secret_reencryption_adapter is None:
            if self._config.require_secret_reencryption_adapter:
                raise RuntimeError(
                    "secret re-encryption adapter is required for rotating SECRET_ENCRYPTION keys with bound secrets; "
                    f"key_id={old_key.key_id} bound_secret_count={len(envelopes)}"
                )
            return len(envelopes), 0
        rekeyed = 0
        for envelope in envelopes:
            ciphertext = self._secret_reencryption_adapter.reencrypt_envelope(
                envelope=envelope,
                old_encryption_key_id=old_key.key_id,
                new_key=new_key,
            )
            self._secret_backend.rekey(
                ref=envelope.record.ref,
                ciphertext=ciphertext,
                encryption_key_id=new_key.key_id,
                now=now,
                expected_row_version=envelope.row_version,
            )
            rekeyed += 1
        return len(envelopes), rekeyed

    def should_rotate_secret(self, *, created_at: datetime, expires_at: datetime | None, compromised: bool, scope_changed: bool, now: datetime) -> bool:
        decision = self._credential_rotation_policy.evaluate(
            created_at=created_at,
            expires_at=expires_at,
            compromised=compromised,
            scope_changed=scope_changed,
            now=now,
        )
        return bool(decision.should_rotate)

    @staticmethod
    def _next_key_id(*, old_key: KeyMaterialRecord, now: datetime) -> str:
        stamp = now.strftime("%Y%m%d%H%M%S")
        base = old_key.key_id.rsplit(":v", 1)[0]
        suffix = secrets.token_hex(4)
        return f"{base}:v{stamp}-{suffix}"


__all__ = [
    "CANON_KEY_ROTATION_SCHEDULER",
    "KeyRotationScheduler",
    "KeyRotationSchedulerConfig",
    "RotationExecution",
    "RotationTask",
    "SecretReencryptionAdapter",
    "StdlibSecretReencryptionAdapter",
]
