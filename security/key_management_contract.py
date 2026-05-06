from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


CANON_KEY_MANAGEMENT_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KeyPurpose(str, Enum):
    SECRET_ENCRYPTION = 'secret_encryption'
    REQUEST_SIGNING = 'request_signing'
    WEBHOOK_VERIFICATION = 'webhook_verification'
    SESSION_SIGNING = 'session_signing'
    TOKEN_SIGNING = 'token_signing'
    SANDBOX_ISOLATION = 'sandbox_isolation'


class KeyStatus(str, Enum):
    ACTIVE = 'active'
    DEPRECATED = 'deprecated'
    REVOKED = 'revoked'
    COMPROMISED = 'compromised'


@dataclass(frozen=True)
class KeyMaterialRecord:
    key_id: str
    purpose: KeyPurpose
    secret_bytes: bytes
    tenant_id: str | None = None
    connector_id: str | None = None
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    activated_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.key_id or '').strip():
            raise ValueError('key_id is required')
        if not isinstance(self.secret_bytes, (bytes, bytearray)) or not bytes(self.secret_bytes):
            raise ValueError('secret_bytes is required')
        if self.created_at.tzinfo is None or self.activated_at.tzinfo is None:
            raise ValueError('key timestamps must be timezone-aware')
        if self.activated_at < self.created_at:
            raise ValueError('activated_at must be >= created_at')
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError('expires_at must be timezone-aware')
        if self.expires_at is not None and self.expires_at <= self.activated_at:
            raise ValueError('expires_at must be > activated_at')

    def is_usable(self, *, at: datetime | None = None) -> bool:
        moment = at or utc_now()
        if moment.tzinfo is None:
            raise ValueError('at must be timezone-aware')
        if self.status is not KeyStatus.ACTIVE:
            return False
        if moment < self.activated_at:
            return False
        if self.expires_at is not None and moment >= self.expires_at:
            return False
        return True


__all__ = [
    'CANON_KEY_MANAGEMENT_CONTRACT',
    'KeyMaterialRecord',
    'KeyPurpose',
    'KeyStatus',
    'utc_now',
]
