from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Protocol

from security.secret_contract import SecretRecord, SecretRef, utc_now


CANON_SECRET_VAULT_BACKEND = True


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class SecretEnvelope:
    record: SecretRecord
    encryption_key_id: str
    version_nonce: str
    row_version: int = 1
    etag: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        self.record.validate()
        if not str(self.encryption_key_id or "").strip():
            raise ValueError("encryption_key_id is required")
        if not str(self.version_nonce or "").strip():
            raise ValueError("version_nonce is required")
        if int(self.row_version) <= 0:
            raise ValueError("row_version must be > 0")


@dataclass(frozen=True)
class SecretLookup:
    tenant_id: str
    secret_name: str
    version: str | None = None
    connector_id: str | None = None
    scope: str | None = None
    include_inactive: bool = False
    as_of: datetime | None = None

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.secret_name or "").strip():
            raise ValueError("secret_name is required")
        if self.version is not None and not str(self.version).strip():
            raise ValueError("version must be non-empty when provided")
        if self.as_of is not None:
            _require_aware(self.as_of, field_name="as_of")


class SecretVaultBackend(Protocol):
    def put(self, envelope: SecretEnvelope, *, expected_row_version: int | None = None) -> SecretEnvelope: ...
    def get(self, ref: SecretRef) -> SecretEnvelope: ...
    def get_latest(self, lookup: SecretLookup) -> SecretEnvelope: ...
    def list_versions(self, lookup: SecretLookup) -> tuple[SecretEnvelope, ...]: ...
    def list_by_encryption_key_id(
        self,
        *,
        encryption_key_id: str,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        limit: int = 500,
    ) -> tuple[SecretEnvelope, ...]: ...
    def deactivate(self, ref: SecretRef, *, compromised: bool = False, now: datetime | None = None) -> SecretEnvelope: ...
    def soft_delete(self, ref: SecretRef, *, now: datetime | None = None) -> SecretEnvelope: ...
    def rekey(
        self,
        *,
        ref: SecretRef,
        ciphertext: bytes,
        encryption_key_id: str,
        now: datetime | None = None,
        expected_row_version: int | None = None,
    ) -> SecretEnvelope: ...


def envelope_is_active(envelope: SecretEnvelope, *, at: datetime | None = None) -> bool:
    envelope.validate()
    moment = at or utc_now()
    _require_aware(moment, field_name="at")
    return envelope.record.is_active(at=moment)


def to_metadata_with_key_binding(
    metadata: Mapping[str, str] | None,
    *,
    encryption_key_id: str,
    version_nonce: str,
) -> dict[str, str]:
    merged = dict(metadata or {})
    merged["encryption_key_id"] = str(encryption_key_id)
    merged["version_nonce"] = str(version_nonce)
    return merged


__all__ = [
    "CANON_SECRET_VAULT_BACKEND",
    "SecretEnvelope",
    "SecretLookup",
    "SecretVaultBackend",
    "envelope_is_active",
    "to_metadata_with_key_binding",
]
