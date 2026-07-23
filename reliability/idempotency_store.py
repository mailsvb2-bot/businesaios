from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence
import json
import os
import threading
import uuid

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
_ACTIVE_STATES = {IdempotencyState.STARTED, IdempotencyState.IN_PROGRESS}
_TERMINAL_STATES = {IdempotencyState.COMPLETED, IdempotencyState.FAILED}
_JOURNAL_FIELD = "_idempotency_journal"


def _merge_metadata(
    base: Mapping[str, Any] | None,
    patch: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base or {})
    if patch:
        merged.update(dict(patch))
    return merged


def _aware_moment(value: datetime | None) -> datetime:
    moment = value or utc_now()
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment


def _positive_ttl(value: int) -> int:
    ttl = int(value)
    if ttl <= 0:
        raise ValueError("lease_ttl_seconds must be > 0")
    return ttl



def _seal_record(record: IdempotencyRecord) -> IdempotencyRecord:
    sealed = replace(
        record,
        metadata=MappingProxyType(dict(record.metadata)),
    )
    sealed.validate()
    return sealed


def _owner_id(value: object) -> str:
    owner = str(value or "").strip()
    if not owner:
        raise ValueError("owner_id is required")
    return owner


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
        owner = _owner_id(owner_id)
        ttl = _positive_ttl(lease_ttl_seconds)
        moment = _aware_moment(now)
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
                    lease_ttl_seconds=ttl,
                    now=moment,
                    increment_attempt=True,
                    metadata_patch=metadata_patch,
                )
                created = _seal_record(created)
                self._records[cache_key] = created
                return IdempotencyDecision(
                    resolution=IdempotencyResolution.ACCEPTED,
                    record=created,
                )

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

            expired = existing.mark_expired(
                now=moment,
                metadata_patch=metadata_patch,
            )
            expired = _seal_record(expired)
            renewed = expired.as_reserved(
                owner_id=owner,
                lease_ttl_seconds=ttl,
                now=moment,
                increment_attempt=True,
                metadata_patch=metadata_patch,
            )
            renewed = _seal_record(renewed)
            self._records[cache_key] = renewed
            return IdempotencyDecision(
                resolution=IdempotencyResolution.ACCEPTED,
                record=renewed,
            )

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
        owner = _owner_id(owner_id)
        ttl = _positive_ttl(lease_ttl_seconds)
        moment = _aware_moment(now)
        with self._lock:
            record = self._require_owned_active(
                key=key,
                owner_id=owner,
                now=moment,
            )
            renewed = record.as_reserved(
                owner_id=owner,
                lease_ttl_seconds=ttl,
                now=moment,
                increment_attempt=False,
                metadata_patch=metadata_patch,
            )
            renewed = _seal_record(renewed)
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
        owner = _owner_id(owner_id)
        moment = _aware_moment(now)
        with self._lock:
            record = self._require_owned_active(
                key=key,
                owner_id=owner,
                now=moment,
            )
            completed = record.mark_completed(
                owner_id=owner,
                result_ref=result_ref,
                result_digest=result_digest,
                now=moment,
                metadata_patch=metadata_patch,
            )
            completed = _seal_record(completed)
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
        owner = _owner_id(owner_id)
        moment = _aware_moment(now)
        with self._lock:
            record = self._require_owned_active(
                key=key,
                owner_id=owner,
                now=moment,
            )
            failed = record.mark_failed(
                owner_id=owner,
                reason=reason,
                now=moment,
                metadata_patch=metadata_patch,
            )
            failed = _seal_record(failed)
            self._records[key.as_tuple()] = failed
            return failed

    def expire_stale(
        self,
        *,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> int:
        moment = _aware_moment(now)
        changed = 0
        with self._lock:
            for cache_key, record in list(self._records.items()):
                if record.state not in _ACTIVE_STATES:
                    continue
                if not record.has_live_lease(now=moment):
                    expired = record.mark_expired(
                        now=moment,
                        metadata_patch=metadata_patch,
                    )
                    expired = _seal_record(expired)
                    self._records[cache_key] = expired
                    changed += 1
        return changed

    def _require_owned_active(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        now: datetime,
    ) -> IdempotencyRecord:
        key.validate()
        record = self._records.get(key.as_tuple())
        if record is None:
            raise KeyError(f"idempotency key not found: {key.as_tuple()}")
        if str(record.owner_id or "") != owner_id:
            raise PermissionError("owner mismatch for idempotency record")
        if record.state in _TERMINAL_STATES:
            raise RuntimeError(
                f"idempotency record is terminal: {record.state.value}"
            )
        if record.state not in _ACTIVE_STATES or not record.has_live_lease(now=now):
            raise PermissionError("idempotency lease is not active")
        return record


class JsonlIdempotencyStore(InMemoryIdempotencyStore):
    """Crash-consistent append journal with cross-process serialization.

    Legacy plain record rows remain readable. New writes are framed as
    begin/record/commit transactions, so an interrupted append is ignored on
    recovery unless its commit marker is durable.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock = threading.RLock()
        self._lock_path = self._path.with_name(f"{self._path.name}.lock")
        with self._lock:
            with self._exclusive_file_lock():
                self._reload_unlocked()

    @staticmethod
    def _row_from_record(record: IdempotencyRecord) -> dict[str, Any]:
        return {
            "tenant_id": record.idempotency_key.tenant_id,
            "namespace": record.idempotency_key.namespace,
            "operation": record.idempotency_key.operation,
            "key": record.idempotency_key.key,
            "scope_hash": record.idempotency_key.scope_hash,
            "state": record.state.value,
            "first_seen_at": record.first_seen_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "lease_expires_at": (
                record.lease_expires_at.isoformat()
                if record.lease_expires_at is not None
                else None
            ),
            "completed_at": (
                record.completed_at.isoformat()
                if record.completed_at is not None
                else None
            ),
            "owner_id": record.owner_id,
            "attempt_count": record.attempt_count,
            "result_ref": record.result_ref,
            "result_digest": record.result_digest,
            "failure_reason": record.failure_reason,
            "metadata": dict(record.metadata),
        }

    @staticmethod
    def _record_from_row(row: Mapping[str, Any]) -> IdempotencyRecord:
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
            lease_expires_at=(
                datetime.fromisoformat(str(row["lease_expires_at"]))
                if row.get("lease_expires_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(str(row["completed_at"]))
                if row.get("completed_at")
                else None
            ),
            owner_id=row.get("owner_id"),
            attempt_count=int(row.get("attempt_count") or 0),
            result_ref=row.get("result_ref"),
            result_digest=row.get("result_digest"),
            failure_reason=row.get("failure_reason"),
            metadata=dict(row.get("metadata") or {}),
        )
        return _seal_record(record)

    def _reload_unlocked(self) -> None:
        records: dict[tuple[str, str, str, str], IdempotencyRecord] = {}
        if not self._path.exists():
            self._records = records
            return
        raw = self._path.read_bytes()
        lines = raw.splitlines(keepends=True)
        pending: dict[str, tuple[int, list[IdempotencyRecord]]] = {}
        offset = 0
        for index, raw_line in enumerate(lines):
            line_start = offset
            offset += len(raw_line)
            is_unterminated_tail = (
                index == len(lines) - 1
                and not raw_line.endswith((b"\n", b"\r"))
            )
            try:
                text = raw_line.decode("utf-8")
                if not text.strip():
                    continue
                row = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError):
                if is_unterminated_tail:
                    self._truncate_unlocked(line_start)
                    break
                raise
            if not isinstance(row, Mapping):
                raise ValueError("idempotency journal row must be an object")
            marker = row.get(_JOURNAL_FIELD)
            if marker is None:
                record = self._record_from_row(row)
                records[record.idempotency_key.as_tuple()] = record
                continue
            tx_id = str(row.get("tx_id") or "")
            if not tx_id:
                raise ValueError("idempotency journal transaction id is required")
            if marker == "begin":
                if tx_id in pending:
                    raise ValueError("duplicate idempotency journal transaction")
                count = int(row.get("count") or 0)
                if count <= 0:
                    raise ValueError("idempotency journal count must be > 0")
                pending[tx_id] = (count, [])
            elif marker == "record":
                if tx_id not in pending:
                    raise ValueError("orphan idempotency journal record")
                payload = row.get("payload")
                if not isinstance(payload, Mapping):
                    raise ValueError("idempotency journal payload must be an object")
                pending[tx_id][1].append(self._record_from_row(payload))
            elif marker == "commit":
                if tx_id not in pending:
                    raise ValueError("orphan idempotency journal commit")
                expected, transaction_records = pending.pop(tx_id)
                if len(transaction_records) != expected:
                    raise ValueError("incomplete idempotency journal transaction")
                for record in transaction_records:
                    records[record.idempotency_key.as_tuple()] = record
            else:
                raise ValueError("unknown idempotency journal marker")
        self._records = records

    def _truncate_unlocked(self, size: int) -> None:
        fd = os.open(self._path, os.O_WRONLY)
        try:
            os.ftruncate(fd, max(0, int(size)))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _needs_separator_unlocked(self) -> bool:
        if not self._path.exists() or self._path.stat().st_size == 0:
            return False
        with self._path.open("rb") as stream:
            stream.seek(-1, os.SEEK_END)
            return stream.read(1) not in {b"\n", b"\r"}

    @contextmanager
    def _exclusive_file_lock(self) -> Iterator[None]:
        with self._file_lock:
            self._lock_path.touch(exist_ok=True)
            with self._lock_path.open("r+b") as lock_file:
                if os.name == "nt":
                    import msvcrt

                    if self._lock_path.stat().st_size == 0:
                        lock_file.write(b"\0")
                        lock_file.flush()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _append_records_unlocked(
        self,
        records: Sequence[IdempotencyRecord],
    ) -> None:
        if not records:
            return
        tx_id = uuid.uuid4().hex
        rows: list[dict[str, Any]] = [
            {_JOURNAL_FIELD: "begin", "tx_id": tx_id, "count": len(records)}
        ]
        rows.extend(
            {
                _JOURNAL_FIELD: "record",
                "tx_id": tx_id,
                "payload": self._row_from_record(record),
            }
            for record in records
        )
        rows.append({_JOURNAL_FIELD: "commit", "tx_id": tx_id})
        payload = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ).encode("utf-8")
        if self._needs_separator_unlocked():
            payload = b"\n" + payload
        fd = os.open(self._path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("idempotency journal write made no progress")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def _run_persisted(self, mutation):
        with self._lock:
            with self._exclusive_file_lock():
                self._reload_unlocked()
                result, changed_records = mutation()
                try:
                    self._append_records_unlocked(changed_records)
                except BaseException:
                    self._reload_unlocked()
                    raise
                return result

    def reserve(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyDecision:
        def mutation():
            decision = super(JsonlIdempotencyStore, self).reserve(
                key=key,
                owner_id=owner_id,
                lease_ttl_seconds=lease_ttl_seconds,
                now=now,
                metadata_patch=metadata_patch,
            )
            changed = (
                [decision.record]
                if decision.resolution is IdempotencyResolution.ACCEPTED
                else []
            )
            return decision, changed

        return self._run_persisted(mutation)

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        with self._lock:
            with self._exclusive_file_lock():
                self._reload_unlocked()
                return super().get(key=key)

    def renew_lease(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        lease_ttl_seconds: int = 300,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        def mutation():
            record = super(JsonlIdempotencyStore, self).renew_lease(
                key=key,
                owner_id=owner_id,
                lease_ttl_seconds=lease_ttl_seconds,
                now=now,
                metadata_patch=metadata_patch,
            )
            return record, [record]

        return self._run_persisted(mutation)

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
        def mutation():
            record = super(JsonlIdempotencyStore, self).mark_completed(
                key=key,
                owner_id=owner_id,
                result_ref=result_ref,
                result_digest=result_digest,
                now=now,
                metadata_patch=metadata_patch,
            )
            return record, [record]

        return self._run_persisted(mutation)

    def mark_failed(
        self,
        *,
        key: IdempotencyKey,
        owner_id: str,
        reason: str | None = None,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> IdempotencyRecord:
        def mutation():
            record = super(JsonlIdempotencyStore, self).mark_failed(
                key=key,
                owner_id=owner_id,
                reason=reason,
                now=now,
                metadata_patch=metadata_patch,
            )
            return record, [record]

        return self._run_persisted(mutation)

    def expire_stale(
        self,
        *,
        now: datetime | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> int:
        def mutation():
            before = dict(self._records)
            changed = super(JsonlIdempotencyStore, self).expire_stale(
                now=now,
                metadata_patch=metadata_patch,
            )
            changed_records = [
                record
                for cache_key, record in self._records.items()
                if before.get(cache_key) != record
            ]
            return changed, changed_records

        return self._run_persisted(mutation)


__all__ = [
    "CANON_IDEMPOTENCY_CONTRACT",
    "CANON_IDEMPOTENCY_STORE",
    "InMemoryIdempotencyStore",
    "JsonlIdempotencyStore",
]
