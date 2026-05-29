from __future__ import annotations

"""Canonical runtime queue contracts.

Operational only:
- persists already-decided work,
- never introduces a second decision center,
- workers must execute an injected canonical runner.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, UTC
from enum import Enum
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id

CANON_RUNTIME_QUEUE_CONTRACT = True

MAX_JOB_ATTEMPTS = 100
MAX_JOB_PAYLOAD_BYTES = 256_000
MAX_JOB_TAGS = 32
MAX_ID_LENGTH = 200
MAX_QUEUE_NAME_LENGTH = 120
MAX_JOB_TYPE_LENGTH = 160
MAX_ERROR_LENGTH = 2_000


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_now(value: datetime | None = None) -> datetime:
    return utc_now() if value is None else _normalize_datetime(value, field_name="now")


def _normalize_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _normalize_optional_datetime(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    return _normalize_datetime(value, field_name=field_name)


def _require_text(value: str, *, field_name: str, max_length: int) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max length {max_length}")
    return text


def _normalize_error(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:MAX_ERROR_LENGTH]


def _normalize_tags(tags: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    raw = tuple(tags or ())
    if len(raw) > MAX_JOB_TAGS:
        raise ValueError(f"too many tags; max allowed is {MAX_JOB_TAGS}")
    return tuple(_require_text(str(tag), field_name="tag", max_length=MAX_ID_LENGTH) for tag in raw)


def _serialized_mapping_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, default=str, separators=(",", ":"))


class JobState(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.DEAD_LETTER, self.CANCELLED}


class JobPriority(int, Enum):
    LOW = 10
    NORMAL = 50
    HIGH = 90
    CRITICAL = 100


@dataclass(frozen=True)
class JobLease:
    owner_id: str
    fencing_token: int
    claimed_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _require_text(self.owner_id, field_name="lease.owner_id", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "fencing_token", int(self.fencing_token))
        object.__setattr__(self, "claimed_at", _normalize_datetime(self.claimed_at, field_name="lease.claimed_at"))
        object.__setattr__(self, "expires_at", _normalize_datetime(self.expires_at, field_name="lease.expires_at"))
        if int(self.fencing_token) <= 0:
            raise ValueError("lease.fencing_token must be > 0")
        if self.expires_at <= self.claimed_at:
            raise ValueError("lease.expires_at must be greater than claimed_at")

    def is_live(self, *, now: datetime | None = None) -> bool:
        return normalize_now(now) < self.expires_at

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return not self.is_live(now=now)


@dataclass(frozen=True)
class JobRecord:
    tenant_id: str
    job_id: str
    queue_name: str
    job_type: str
    payload: Mapping[str, Any]
    dedupe_key: str
    run_at: datetime
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    priority: int = int(JobPriority.NORMAL)
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_attempts: int = 8
    last_error: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    lease: JobLease | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        object.__setattr__(self, "job_id", _require_text(self.job_id, field_name="job_id", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "queue_name", _require_text(self.queue_name, field_name="queue_name", max_length=MAX_QUEUE_NAME_LENGTH))
        object.__setattr__(self, "job_type", _require_text(self.job_type, field_name="job_type", max_length=MAX_JOB_TYPE_LENGTH))
        object.__setattr__(self, "dedupe_key", _require_text(self.dedupe_key, field_name="dedupe_key", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "run_at", _normalize_datetime(self.run_at, field_name="run_at"))
        object.__setattr__(self, "created_at", _normalize_datetime(self.created_at, field_name="created_at"))
        object.__setattr__(self, "updated_at", _normalize_datetime(self.updated_at, field_name="updated_at"))
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        object.__setattr__(self, "last_error", _normalize_error(self.last_error))
        if self.correlation_id is not None:
            object.__setattr__(self, "correlation_id", _require_text(self.correlation_id, field_name="correlation_id", max_length=MAX_ID_LENGTH))
        if self.causation_id is not None:
            object.__setattr__(self, "causation_id", _require_text(self.causation_id, field_name="causation_id", max_length=MAX_ID_LENGTH))
        if self.lease is not None:
            object.__setattr__(self, "lease", JobLease(
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                claimed_at=self.lease.claimed_at,
                expires_at=self.lease.expires_at,
            ))
        self.validate()

    def validate(self) -> None:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        if self.priority < int(JobPriority.LOW) or self.priority > int(JobPriority.CRITICAL):
            raise ValueError("priority is out of allowed range")
        if self.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if self.max_attempts < 1 or self.max_attempts > MAX_JOB_ATTEMPTS:
            raise ValueError(f"max_attempts must be within 1..{MAX_JOB_ATTEMPTS}")
        if len(self.serialized_payload().encode("utf-8")) > MAX_JOB_PAYLOAD_BYTES:
            raise ValueError("payload is too large")
        if self.attempts > self.max_attempts:
            raise ValueError("attempts must be <= max_attempts")
        if self.lease is not None and self.state is not JobState.CLAIMED:
            raise ValueError("lease can only exist for claimed jobs")
        if self.state is JobState.CLAIMED and self.lease is None:
            raise ValueError("claimed jobs must have a lease")

    def serialized_payload(self) -> str:
        return _serialized_mapping_payload(self.payload)

    def is_due(self, *, now: datetime | None = None) -> bool:
        return self.run_at <= normalize_now(now)

    def is_claimable(self, *, now: datetime | None = None) -> bool:
        if self.state is JobState.CLAIMED:
            return self.lease is not None and self.lease.is_expired(now=now) and self.is_due(now=now)
        if self.state is not JobState.PENDING:
            return False
        return self.is_due(now=now)

    def can_retry_after_failure(self) -> bool:
        return int(self.attempts) < int(self.max_attempts)


@dataclass(frozen=True)
class JobDispatchRequest:
    tenant_id: str
    job_id: str
    queue_name: str
    job_type: str
    payload: Mapping[str, Any]
    dedupe_key: str
    delay_seconds: int = 0
    priority: int = int(JobPriority.NORMAL)
    max_attempts: int = 8
    correlation_id: str | None = None
    causation_id: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        object.__setattr__(self, "job_id", _require_text(self.job_id, field_name="job_id", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "queue_name", _require_text(self.queue_name, field_name="queue_name", max_length=MAX_QUEUE_NAME_LENGTH))
        object.__setattr__(self, "job_type", _require_text(self.job_type, field_name="job_type", max_length=MAX_JOB_TYPE_LENGTH))
        object.__setattr__(self, "dedupe_key", _require_text(self.dedupe_key, field_name="dedupe_key", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "delay_seconds", max(0, int(self.delay_seconds)))
        object.__setattr__(self, "priority", int(self.priority))
        object.__setattr__(self, "max_attempts", int(self.max_attempts))
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        if self.correlation_id is not None:
            object.__setattr__(self, "correlation_id", _require_text(self.correlation_id, field_name="correlation_id", max_length=MAX_ID_LENGTH))
        if self.causation_id is not None:
            object.__setattr__(self, "causation_id", _require_text(self.causation_id, field_name="causation_id", max_length=MAX_ID_LENGTH))
        if self.priority < int(JobPriority.LOW) or self.priority > int(JobPriority.CRITICAL):
            raise ValueError("priority is out of allowed range")
        if self.max_attempts < 1 or self.max_attempts > MAX_JOB_ATTEMPTS:
            raise ValueError(f"max_attempts must be within 1..{MAX_JOB_ATTEMPTS}")
        if len(_serialized_mapping_payload(self.payload).encode("utf-8")) > MAX_JOB_PAYLOAD_BYTES:
            raise ValueError("payload is too large")

    def to_record(self, *, now: datetime | None = None) -> JobRecord:
        moment = normalize_now(now)
        return JobRecord(
            tenant_id=self.tenant_id,
            job_id=self.job_id,
            queue_name=self.queue_name,
            job_type=self.job_type,
            payload=dict(self.payload),
            dedupe_key=self.dedupe_key,
            run_at=moment + timedelta(seconds=self.delay_seconds),
            created_at=moment,
            updated_at=moment,
            priority=self.priority,
            max_attempts=self.max_attempts,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            tags=self.tags,
        )


@dataclass(frozen=True)
class JobResult:
    ok: bool
    status: str
    job_id: str
    tenant_id: str
    attempts: int
    output: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    retry_delay_seconds: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", _require_text(self.job_id, field_name="job_id", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        object.__setattr__(self, "status", _require_text(self.status, field_name="status", max_length=MAX_ID_LENGTH))
        object.__setattr__(self, "error", _normalize_error(self.error))
        if self.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if not isinstance(self.output, Mapping):
            raise TypeError("output must be a mapping")
        if self.retry_delay_seconds is not None:
            retry_delay_seconds = int(self.retry_delay_seconds)
            if retry_delay_seconds < 0:
                raise ValueError("retry_delay_seconds must be >= 0")
            object.__setattr__(self, "retry_delay_seconds", retry_delay_seconds)


__all__ = [
    "CANON_RUNTIME_QUEUE_CONTRACT",
    "JobDispatchRequest",
    "JobLease",
    "JobPriority",
    "JobRecord",
    "JobResult",
    "JobState",
    "MAX_ERROR_LENGTH",
    "MAX_JOB_ATTEMPTS",
    "MAX_JOB_PAYLOAD_BYTES",
    "MAX_JOB_TAGS",
    "normalize_now",
    "utc_now",
]
