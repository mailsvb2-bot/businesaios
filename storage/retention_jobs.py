from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol


CANON_STORAGE_RETENTION_JOBS = True


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class RetentionPolicy:
    audit_retention_days: int = 365
    evidence_retention_days: int = 365

    def validate(self) -> None:
        if int(self.audit_retention_days) < 1:
            raise ValueError("audit_retention_days must be >= 1")
        if int(self.evidence_retention_days) < 1:
            raise ValueError("evidence_retention_days must be >= 1")

    def retention_until_for_audit(self, *, created_at: datetime | None = None) -> datetime:
        self.validate()
        base = created_at or utc_now()
        if base.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return base + timedelta(days=int(self.audit_retention_days))

    def retention_until_for_evidence(self, *, created_at: datetime | None = None) -> datetime:
        self.validate()
        base = created_at or utc_now()
        if base.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return base + timedelta(days=int(self.evidence_retention_days))


class ExpiringStore(Protocol):
    def delete_expired(self, *, now: datetime | None = None) -> int: ...


@dataclass(frozen=True)
class RetentionJobReport:
    started_at: datetime
    completed_at: datetime
    audit_deleted: int = 0
    evidence_deleted: int = 0
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def total_deleted(self) -> int:
        return int(self.audit_deleted) + int(self.evidence_deleted)


class StorageRetentionJobRunner:
    def __init__(
        self,
        *,
        audit_store: ExpiringStore | None = None,
        evidence_store: ExpiringStore | None = None,
    ) -> None:
        self._audit_store = audit_store
        self._evidence_store = evidence_store

    def run(self, *, now: datetime | None = None, labels: dict[str, str] | None = None) -> RetentionJobReport:
        started_at = now or utc_now()
        if started_at.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        audit_deleted = 0 if self._audit_store is None else int(self._audit_store.delete_expired(now=started_at))
        evidence_deleted = 0 if self._evidence_store is None else int(self._evidence_store.delete_expired(now=started_at))
        completed_at = utc_now()
        return RetentionJobReport(
            started_at=started_at,
            completed_at=completed_at,
            audit_deleted=audit_deleted,
            evidence_deleted=evidence_deleted,
            labels={str(k): str(v) for k, v in dict(labels or {}).items()},
        )


__all__ = [
    "CANON_STORAGE_RETENTION_JOBS",
    "ExpiringStore",
    "RetentionJobReport",
    "RetentionPolicy",
    "StorageRetentionJobRunner",
    "utc_now",
]
