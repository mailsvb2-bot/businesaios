from __future__ import annotations

"""Canonical idempotency contract for reliability.

Infra-only. No business decision logic.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Protocol

from core.tenancy.normalization import require_tenant_id


CANON_IDEMPOTENCY_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IdempotencyState(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class IdempotencyResolution(str, Enum):
    ACCEPTED = "accepted"
    REPLAY_COMPLETED = "replay_completed"
    REJECTED_IN_PROGRESS = "rejected_in_progress"
    REJECTED_SCOPE_MISMATCH = "rejected_scope_mismatch"
    REJECTED_TERMINAL_FAILED = "rejected_terminal_failed"


@dataclass(frozen=True)
class IdempotencyKey:
    tenant_id: str
    namespace: str
    operation: str
    key: str
    scope_hash: str = ""

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.namespace or "").strip():
            raise ValueError("namespace is required")
        if not str(self.operation or "").strip():
            raise ValueError("operation is required")
        if not str(self.key or "").strip():
            raise ValueError("key is required")

    def as_tuple(self) -> tuple[str, str, str, str]:
        self.validate()
        return (
            str(self.tenant_id).strip(),
            str(self.namespace).strip(),
            str(self.operation).strip(),
            str(self.key).strip(),
        )

    def same_scope(self, other: "IdempotencyKey") -> bool:
        self.validate()
        other.validate()
        return self.as_tuple() == other.as_tuple() and str(self.scope_hash or "") == str(other.scope_hash or "")


@dataclass(frozen=True)
class IdempotencyRecord:
    idempotency_key: IdempotencyKey
    state: IdempotencyState
    first_seen_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    owner_id: str | None = None
    attempt_count: int = 0
    result_ref: str | None = None
    result_digest: str | None = None
    failure_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.idempotency_key.validate()
        if self.first_seen_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.updated_at < self.first_seen_at:
            raise ValueError("updated_at must be >= first_seen_at")
        if self.lease_expires_at is not None and self.lease_expires_at.tzinfo is None:
            raise ValueError("lease_expires_at must be timezone-aware")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")
        if int(self.attempt_count) < 0:
            raise ValueError("attempt_count must be >= 0")

    def has_live_lease(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self.lease_expires_at is not None and moment < self.lease_expires_at

    def is_terminal(self) -> bool:
        return self.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED}

    def can_be_stolen_after_expiry(self, *, now: datetime | None = None) -> bool:
        if self.state not in {IdempotencyState.STARTED, IdempotencyState.IN_PROGRESS, IdempotencyState.EXPIRED}:
            return False
        return not self.has_live_lease(now=now)

    def as_reserved(
        self,
        *,
        owner_id: str,
        lease_ttl_seconds: int,
        now: datetime | None = None,
        increment_attempt: bool,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> "IdempotencyRecord":
        moment = now or utc_now()
        lease = moment + timedelta(seconds=max(1, int(lease_ttl_seconds)))
        metadata = dict(self.metadata)
        if metadata_patch:
            metadata.update(dict(metadata_patch))
        return replace(
            self,
            state=IdempotencyState.IN_PROGRESS,
            updated_at=moment,
            lease_expires_at=lease,
            owner_id=str(owner_id),
            attempt_count=int(self.attempt_count) + (1 if increment_attempt else 0),
            failure_reason=None,
            metadata=metadata,
        )

    def mark_completed(
        self,
        *,
        owner_id: str,
        result_ref: str | None = None,
        result_digest: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> "IdempotencyRecord":
        moment = now or utc_now()
        metadata = dict(self.metadata)
        if metadata_patch:
            metadata.update(dict(metadata_patch))
        return replace(
            self,
            state=IdempotencyState.COMPLETED,
            updated_at=moment,
            completed_at=moment,
            lease_expires_at=None,
            owner_id=str(owner_id),
            result_ref=result_ref if result_ref is not None else self.result_ref,
            result_digest=result_digest if result_digest is not None else self.result_digest,
            failure_reason=None,
            metadata=metadata,
        )

    def mark_failed(
        self,
        *,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> "IdempotencyRecord":
        moment = now or utc_now()
        metadata = dict(self.metadata)
        if metadata_patch:
            metadata.update(dict(metadata_patch))
        return replace(
            self,
            state=IdempotencyState.FAILED,
            updated_at=moment,
            lease_expires_at=None,
            owner_id=str(owner_id),
            failure_reason=None if reason is None else str(reason),
            metadata=metadata,
        )

    def mark_expired(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> "IdempotencyRecord":
        moment = now or utc_now()
        metadata = dict(self.metadata)
        if metadata_patch:
            metadata.update(dict(metadata_patch))
        return replace(
            self,
            state=IdempotencyState.EXPIRED,
            updated_at=moment,
            lease_expires_at=None,
            metadata=metadata,
        )


@dataclass(frozen=True)
class IdempotencyDecision:
    resolution: IdempotencyResolution
    record: IdempotencyRecord
    replay_result_ref: str | None = None
    replay_result_digest: str | None = None


class IdempotencyStore(Protocol):
    def reserve(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyDecision: ...

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None: ...

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord: ...

    def mark_completed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        result_ref: str | None = None,
        result_digest: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord: ...

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord: ...

    def expire_stale(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> int: ...
