from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import json
import threading

from reliability.idempotency_contract import (
    CANON_IDEMPOTENCY_CONTRACT,
    IdempotencyDecision,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyResolution,
    IdempotencyState,
    IdempotencyStore,
    utc_now,
)


CANON_IDEMPOTENCY_STORE = True


def _merge_metadata(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    if patch:
        merged.update(dict(patch))
    return merged


class InMemoryIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], IdempotencyRecord] = {}
        self._lock = threading.RLock()

    def reserve(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyDecision:
        key.validate()
        owner = str(owner_id).strip()
        if not owner:
            raise ValueError("owner_id is required")
        moment = now or utc_now()
        cache_key = key.as_tuple()
        with self._lock:
            existing = self._records.get(cache_key)
            if existing is None:
                created = IdempotencyRecord(
                    idempotency_key=key,
                    state=IdempotencyState.STARTED,
                    first_seen_at=moment,
                    updated_at=moment,
                    owner_id=owner,
                    attempt_count=0,
                    metadata=_merge_metadata(None, metadata_patch),
                ).as_reserved(
                    owner_id=owner,
                    lease_ttl_seconds=lease_ttl_seconds,
                    now=moment,
                    increment_attempt=True,
                    metadata_patch=metadata_patch,
                )
                self._records[cache_key] = created
                return IdempotencyDecision(resolution=IdempotencyResolution.ACCEPTED, record=created)

            if not existing.idempotency_key.same_scope(key):
                return IdempotencyDecision(
                    resolution=IdempotencyResolution.REJECTED_SCOPE_MISMATCH,
                    record=existing,
                )

            if existing.state is IdempotencyState.COMPLETED:
                return IdempotencyDecision(
                    resolution=IdempotencyResolution.REPLAY_COMPLETED,
                    record=existing,
                    replay_result_ref=existing.result_ref,
                    replay_result_digest=existing.result_digest,
                )

            if existing.state is IdempotencyState.FAILED:
                return IdempotencyDecision(
                    resolution=IdempotencyResolution.REJECTED_TERMINAL_FAILED,
                    record=existing,
                )

            if existing.has_live_lease(now=moment):
                return IdempotencyDecision(
                    resolution=IdempotencyResolution.REJECTED_IN_PROGRESS,
                    record=existing,
                )

            expired = existing.mark_expired(now=moment, metadata_patch=metadata_patch)
            self._records[cache_key] = expired
            renewed = expired.as_reserved(
                owner_id=owner,
                lease_ttl_seconds=lease_ttl_seconds,
                now=moment,
                increment_attempt=True,
                metadata_patch=metadata_patch,
            )
            self._records[cache_key] = renewed
            return IdempotencyDecision(resolution=IdempotencyResolution.ACCEPTED, record=renewed)

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        key.validate()
        with self._lock:
            return self._records.get(key.as_tuple())

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        with self._lock:
            record = self._require_owned_non_terminal(key=key, owner_id=owner_id)
            renewed = record.as_reserved(
                owner_id=str(owner_id),
                lease_ttl_seconds=lease_ttl_seconds,
                now=now or utc_now(),
                increment_attempt=False,
                metadata_patch=metadata_patch,
            )
            self._records[key.as_tuple()] = renewed
            return renewed

    def mark_completed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        result_ref: str | None = None,
        result_digest: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        with self._lock:
            record = self._require_owned_non_terminal(key=key, owner_id=owner_id)
            completed = record.mark_completed(
                owner_id=str(owner_id),
                result_ref=result_ref,
                result_digest=result_digest,
                now=now or utc_now(),
                metadata_patch=metadata_patch,
            )
            self._records[key.as_tuple()] = completed
            return completed

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        with self._lock:
            record = self._require_owned_non_terminal(key=key, owner_id=owner_id)
            failed = record.mark_failed(
                owner_id=str(owner_id),
                reason=reason,
                now=now or utc_now(),
                metadata_patch=metadata_patch,
            )
            self._records[key.as_tuple()] = failed
            return failed

    def expire_stale(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> int:
        moment = now or utc_now()
        changed = 0
        with self._lock:
            for cache_key, record in list(self._records.items()):
                if record.state in {IdempotencyState.COMPLETED, IdempotencyState.FAILED, IdempotencyState.EXPIRED}:
                    continue
                if not record.has_live_lease(now=moment):
                    self._records[cache_key] = record.mark_expired(now=moment, metadata_patch=metadata_patch)
                    changed += 1
        return changed

    def _require_owned_non_terminal(self, *, key: IdempotencyKey, owner_id: str) -> IdempotencyRecord:
        key.validate()
        record = self._records.get(key.as_tuple())
        if record is None:
            raise KeyError(f"idempotency key not found: {key.as_tuple()}")
        if str(record.owner_id or "") != str(owner_id):
            raise PermissionError("owner mismatch for idempotency record")
        if record.is_terminal():
            raise RuntimeError(f"idempotency record is terminal: {record.state.value}")
        return record


__all__ = [
    "CANON_IDEMPOTENCY_CONTRACT",
    "CANON_IDEMPOTENCY_STORE",
    "InMemoryIdempotencyStore",
    "JsonlIdempotencyStore",
]


class JsonlIdempotencyStore(InMemoryIdempotencyStore):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock = threading.RLock()
        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                key = IdempotencyKey(
                    tenant_id=str(row["tenant_id"]),
                    namespace=str(row["namespace"]),
                    operation=str(row["operation"]),
                    key=str(row["key"]),
                    scope_hash=str(row.get("scope_hash") or ""),
                )
                record = IdempotencyRecord(
                    idempotency_key=key,
                    state=IdempotencyState(str(row["state"])),
                    first_seen_at=datetime.fromisoformat(str(row["first_seen_at"])),
                    updated_at=datetime.fromisoformat(str(row["updated_at"])),
                    lease_expires_at=datetime.fromisoformat(str(row["lease_expires_at"])) if row.get("lease_expires_at") else None,
                    completed_at=datetime.fromisoformat(str(row["completed_at"])) if row.get("completed_at") else None,
                    owner_id=row.get("owner_id"),
                    attempt_count=int(row.get("attempt_count") or 0),
                    result_ref=row.get("result_ref"),
                    result_digest=row.get("result_digest"),
                    failure_reason=row.get("failure_reason"),
                    metadata=dict(row.get("metadata") or {}),
                )
                record.validate()
                self._records[key.as_tuple()] = record

    def _append_record(self, record: IdempotencyRecord) -> None:
        row = {
            "tenant_id": record.idempotency_key.tenant_id,
            "namespace": record.idempotency_key.namespace,
            "operation": record.idempotency_key.operation,
            "key": record.idempotency_key.key,
            "scope_hash": record.idempotency_key.scope_hash,
            "state": record.state.value,
            "first_seen_at": record.first_seen_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "lease_expires_at": record.lease_expires_at.isoformat() if record.lease_expires_at is not None else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at is not None else None,
            "owner_id": record.owner_id,
            "attempt_count": record.attempt_count,
            "result_ref": record.result_ref,
            "result_digest": record.result_digest,
            "failure_reason": record.failure_reason,
            "metadata": dict(record.metadata),
        }
        with self._file_lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()

    def reserve(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyDecision:
        decision = super().reserve(
            key=key,
            owner_id=owner_id,
            lease_ttl_seconds=lease_ttl_seconds,
            now=now,
            metadata_patch=metadata_patch,
        )
        self._append_record(decision.record)
        return decision

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        record = super().renew_lease(
            key=key,
            owner_id=owner_id,
            lease_ttl_seconds=lease_ttl_seconds,
            now=now,
            metadata_patch=metadata_patch,
        )
        self._append_record(record)
        return record

    def mark_completed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        result_ref: str | None = None,
        result_digest: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        record = super().mark_completed(
            key=key,
            owner_id=owner_id,
            result_ref=result_ref,
            result_digest=result_digest,
            now=now,
            metadata_patch=metadata_patch,
        )
        self._append_record(record)
        return record

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        record = super().mark_failed(key=key, owner_id=owner_id, reason=reason, now=now, metadata_patch=metadata_patch)
        self._append_record(record)
        return record

    def expire_stale(self, *, now: datetime | None = None, metadata_patch: Mapping[str, Any] | None = None) -> int:
        with self._lock:
            before = {k: v for k, v in self._records.items()}
        changed = super().expire_stale(now=now, metadata_patch=metadata_patch)
        if changed:
            with self._lock:
                for key, record in self._records.items():
                    if before.get(key) is not record:
                        self._append_record(record)
        return changed
