from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Protocol

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus, utc_now


CANON_KEY_PROVIDER_BACKEND = True


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class KeyScope:
    purpose: KeyPurpose
    tenant_id: str | None = None
    connector_id: str | None = None

    def validate(self) -> None:
        if self.tenant_id is not None and not str(self.tenant_id).strip():
            raise ValueError("tenant_id must be non-empty when provided")
        if self.connector_id is not None and not str(self.connector_id).strip():
            raise ValueError("connector_id must be non-empty when provided")


@dataclass(frozen=True)
class KeyQuery:
    scope: KeyScope
    include_inactive: bool = False
    as_of: datetime | None = None

    def validate(self) -> None:
        self.scope.validate()
        if self.as_of is not None:
            _require_aware(self.as_of, field_name="as_of")


@dataclass(frozen=True)
class KeyStatusChange:
    key_id: str
    from_status: KeyStatus
    to_status: KeyStatus
    changed_at: datetime
    metadata_patch: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.key_id or "").strip():
            raise ValueError("key_id is required")
        _require_aware(self.changed_at, field_name="changed_at")


@dataclass(frozen=True)
class KeyRotationCandidate:
    record: KeyMaterialRecord
    due_reason: str
    due_at: datetime
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        self.record.validate()
        if not str(self.due_reason or "").strip():
            raise ValueError("due_reason is required")
        _require_aware(self.due_at, field_name="due_at")


class KeyProviderBackend(Protocol):
    def upsert(self, record: KeyMaterialRecord) -> KeyMaterialRecord: ...
    def get(self, key_id: str) -> KeyMaterialRecord: ...
    def list(self, query: KeyQuery) -> tuple[KeyMaterialRecord, ...]: ...
    def get_active(self, query: KeyQuery) -> KeyMaterialRecord: ...
    def apply_status_change(self, change: KeyStatusChange) -> KeyMaterialRecord: ...
    def rotate(
        self,
        *,
        old_key_id: str,
        new_record: KeyMaterialRecord,
        rotated_at: datetime | None = None,
    ) -> tuple[KeyMaterialRecord, KeyMaterialRecord]: ...
    def list_due_for_rotation(
        self,
        *,
        max_age: timedelta,
        now: datetime | None = None,
        limit: int = 100,
    ) -> tuple[KeyRotationCandidate, ...]: ...


def filter_records(records: Iterable[KeyMaterialRecord], *, query: KeyQuery) -> tuple[KeyMaterialRecord, ...]:
    query.validate()
    moment = query.as_of or utc_now()
    _require_aware(moment, field_name="as_of")
    matched: list[KeyMaterialRecord] = []
    for record in records:
        record.validate()
        if record.purpose is not query.scope.purpose:
            continue
        if query.scope.tenant_id is not None and record.tenant_id != query.scope.tenant_id:
            continue
        if query.scope.connector_id is not None and record.connector_id != query.scope.connector_id:
            continue
        if not query.include_inactive and not record.is_usable(at=moment):
            continue
        matched.append(record)
    matched.sort(
        key=lambda item: (
            item.status is KeyStatus.ACTIVE,
            item.activated_at,
            item.created_at,
            item.key_id,
        ),
        reverse=True,
    )
    return tuple(matched)


def select_best_active_key(records: Iterable[KeyMaterialRecord], *, query: KeyQuery) -> KeyMaterialRecord:
    matched = filter_records(records, query=query)
    if not matched:
        raise KeyError(
            "no key found for "
            f"purpose={query.scope.purpose.value} "
            f"tenant_id={query.scope.tenant_id!r} "
            f"connector_id={query.scope.connector_id!r}"
        )
    return matched[0]


def build_rotation_candidate(
    *,
    record: KeyMaterialRecord,
    max_age: timedelta,
    now: datetime | None = None,
) -> KeyRotationCandidate | None:
    record.validate()
    if max_age <= timedelta(0):
        raise ValueError("max_age must be > 0")
    moment = now or utc_now()
    _require_aware(moment, field_name="now")
    if record.status not in {KeyStatus.ACTIVE, KeyStatus.DEPRECATED}:
        return None
    age_due_at = record.created_at + max_age
    if moment >= age_due_at:
        return KeyRotationCandidate(
            record=record,
            due_reason="max_age_exceeded",
            due_at=age_due_at,
            metadata={"key_id": record.key_id},
        )
    if record.expires_at is not None and moment >= record.expires_at:
        return KeyRotationCandidate(
            record=record,
            due_reason="expired",
            due_at=record.expires_at,
            metadata={"key_id": record.key_id},
        )
    return None


__all__ = [
    "CANON_KEY_PROVIDER_BACKEND",
    "KeyProviderBackend",
    "KeyQuery",
    "KeyRotationCandidate",
    "KeyScope",
    "KeyStatusChange",
    "build_rotation_candidate",
    "filter_records",
    "select_best_active_key",
]
