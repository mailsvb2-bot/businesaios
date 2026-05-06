from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Protocol

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_ADMISSION_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text


@dataclass(frozen=True)
class TenantAdmissionRequest:
    tenant_id: str
    run_id: str
    owner_id: str
    ttl_seconds: int
    labels: Mapping[str, str] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        normalize_text(self.run_id, field_name='run_id')
        normalize_text(self.owner_id, field_name='owner_id')
        if int(self.ttl_seconds) <= 0:
            raise ValueError('ttl_seconds must be > 0')
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError('requested_at must be timezone-aware')
        for key, value in dict(self.labels).items():
            normalize_text(key, field_name='label key')
            normalize_text(value, field_name='label value')


@dataclass(frozen=True)
class TenantAdmissionLease:
    tenant_id: str
    run_id: str
    owner_id: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        normalize_text(self.run_id, field_name='run_id')
        normalize_text(self.owner_id, field_name='owner_id')
        if int(self.fencing_token) <= 0:
            raise ValueError('fencing_token must be > 0')
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError('acquired_at must be timezone-aware')
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError('expires_at must be timezone-aware')
        if self.expires_at <= self.acquired_at:
            raise ValueError('expires_at must be > acquired_at')


@dataclass(frozen=True)
class TenantAdmissionVerdict:
    allowed: bool
    reason: str
    tenant_id: str
    run_id: str
    active_runs: int
    limit: int
    lease: TenantAdmissionLease | None = None


class TenantAdmissionBackend(Protocol):
    def admit(self, *, request: TenantAdmissionRequest, limit: int) -> TenantAdmissionVerdict: ...
    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int) -> TenantAdmissionLease: ...
    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool: ...
    def list_active(self, *, tenant_id: str) -> tuple[TenantAdmissionLease, ...]: ...


__all__ = [
    'CANON_TENANT_ADMISSION_CONTRACT',
    'TenantAdmissionBackend',
    'TenantAdmissionLease',
    'TenantAdmissionRequest',
    'TenantAdmissionVerdict',
    'normalize_text',
    'utc_now',
]
