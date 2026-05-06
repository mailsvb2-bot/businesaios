from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


CANON_SECRET_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SecretSource(str, Enum):
    ENV = 'env'
    MEMORY = 'memory'
    FILE = 'file'
    VAULT = 'vault'
    KMS = 'kms'
    CONNECTOR = 'connector'
    UNKNOWN = 'unknown'


class SecretState(str, Enum):
    ACTIVE = 'active'
    DISABLED = 'disabled'
    DELETED = 'deleted'
    COMPROMISED = 'compromised'


@dataclass(frozen=True)
class SecretRef:
    tenant_id: str
    secret_name: str
    version: str = 'current'
    connector_id: str | None = None
    scope: str | None = None

    def validate(self) -> None:
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.secret_name or '').strip():
            raise ValueError('secret_name is required')
        if not str(self.version or '').strip():
            raise ValueError('version is required')

    def key(self) -> str:
        connector = str(self.connector_id or '').strip() or '*'
        scope = str(self.scope or '').strip() or '*'
        return f"{self.tenant_id}:{connector}:{scope}:{self.secret_name}:{self.version}"


@dataclass(frozen=True)
class SecretRecord:
    ref: SecretRef
    ciphertext: bytes
    source: SecretSource = SecretSource.UNKNOWN
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    rotated_at: datetime | None = None
    deleted_at: datetime | None = None
    expires_at: datetime | None = None
    state: SecretState = SecretState.ACTIVE
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        self.ref.validate()
        if not isinstance(self.ciphertext, (bytes, bytearray)) or not bytes(self.ciphertext):
            raise ValueError('ciphertext is required')
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError('secret timestamps must be timezone-aware')
        if self.updated_at < self.created_at:
            raise ValueError('updated_at must be >= created_at')
        if self.rotated_at is not None:
            if self.rotated_at.tzinfo is None:
                raise ValueError('rotated_at must be timezone-aware')
            if self.rotated_at < self.created_at:
                raise ValueError('rotated_at must be >= created_at')
        if self.deleted_at is not None:
            if self.deleted_at.tzinfo is None:
                raise ValueError('deleted_at must be timezone-aware')
            if self.deleted_at < self.created_at:
                raise ValueError('deleted_at must be >= created_at')
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError('expires_at must be timezone-aware')
            if self.expires_at <= self.created_at:
                raise ValueError('expires_at must be > created_at')

    def is_active(self, *, at: datetime | None = None) -> bool:
        moment = at or utc_now()
        if moment.tzinfo is None:
            raise ValueError('at must be timezone-aware')
        if self.state is not SecretState.ACTIVE:
            return False
        if self.deleted_at is not None and moment >= self.deleted_at:
            return False
        if self.expires_at is not None and moment >= self.expires_at:
            return False
        return True

    def mark_rotated(self, *, now: datetime | None = None) -> 'SecretRecord':
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        return replace(self, updated_at=moment, rotated_at=moment)

    def disable(self, *, now: datetime | None = None, compromised: bool = False) -> 'SecretRecord':
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        state = SecretState.COMPROMISED if compromised else SecretState.DISABLED
        return replace(self, updated_at=moment, state=state)

    def soft_delete(self, *, now: datetime | None = None) -> 'SecretRecord':
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        return replace(self, updated_at=moment, deleted_at=moment, state=SecretState.DELETED)


__all__ = [
    'CANON_SECRET_CONTRACT',
    'SecretRecord',
    'SecretRef',
    'SecretSource',
    'SecretState',
    'utc_now',
]
