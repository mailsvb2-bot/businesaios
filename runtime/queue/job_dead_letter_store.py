from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from runtime.queue.job_contract import MAX_ERROR_LENGTH, JobRecord, normalize_now, utc_now

CANON_RUNTIME_QUEUE_DEAD_LETTER_STORE = True


@dataclass(frozen=True)
class DeadLetterRecord:
    tenant_id: str
    job_id: str
    queue_name: str
    job_type: str
    reason: str
    failed_at: datetime = field(default_factory=utc_now)
    attempts: int = 0
    last_error: str | None = None
    original_job: JobRecord | None = None


class JobDeadLetterStore(Protocol):
    def put(self, record: DeadLetterRecord) -> DeadLetterRecord: ...
    def get(self, *, tenant_id: str, job_id: str) -> DeadLetterRecord | None: ...
    def list_for_queue(self, *, tenant_id: str, queue_name: str, limit: int = 100) -> tuple[DeadLetterRecord, ...]: ...


class InMemoryJobDeadLetterStore(JobDeadLetterStore):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], DeadLetterRecord] = {}
        self._lock = RLock()

    def put(self, record: DeadLetterRecord) -> DeadLetterRecord:
        tenant_id = require_tenant_id(record.tenant_id)
        job_id = str(record.job_id).strip()
        if not job_id:
            raise ValueError("job_id is required")
        queue_name = str(record.queue_name).strip()
        job_type = str(record.job_type).strip()
        if not queue_name:
            raise ValueError("queue_name is required")
        if not job_type:
            raise ValueError("job_type is required")
        reason = str(record.reason).strip() or "dead_lettered"
        if record.original_job is not None:
            if require_tenant_id(record.original_job.tenant_id) != tenant_id:
                raise ValueError("original_job tenant_id must match dead-letter tenant_id")
            if str(record.original_job.job_id).strip() != job_id:
                raise ValueError("original_job job_id must match dead-letter job_id")
        stored = DeadLetterRecord(
            tenant_id=tenant_id,
            job_id=job_id,
            queue_name=queue_name,
            job_type=job_type,
            reason=reason,
            failed_at=normalize_now(record.failed_at),
            attempts=max(0, int(record.attempts)),
            last_error=None if record.last_error is None else str(record.last_error).strip()[:MAX_ERROR_LENGTH] or None,
            original_job=record.original_job,
        )
        with self._lock:
            self._records[(tenant_id, job_id)] = stored
        return stored

    def get(self, *, tenant_id: str, job_id: str) -> DeadLetterRecord | None:
        with self._lock:
            return self._records.get((require_tenant_id(tenant_id), str(job_id).strip()))

    def list_for_queue(self, *, tenant_id: str, queue_name: str, limit: int = 100) -> tuple[DeadLetterRecord, ...]:
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        with self._lock:
            items = [
                record
                for (item_tenant_id, _), record in self._records.items()
                if item_tenant_id == tid and record.queue_name == qn
            ]
        items.sort(key=lambda item: (-item.failed_at.timestamp(), item.job_id))
        return tuple(items[: max(0, int(limit))])




def runtime_dead_letter_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_JOB_DEAD_LETTER_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "runtime" / "job_dead_letters.json"


class PersistentJobDeadLetterStore(InMemoryJobDeadLetterStore):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else runtime_dead_letter_store_path()
        super().__init__()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def put(self, record: DeadLetterRecord) -> DeadLetterRecord:
        saved = super().put(record)
        self._flush()
        return saved

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"records": []})
        items = raw.get("records", []) if isinstance(raw, dict) else []
        self._records = {}
        for payload in items:
            record = from_dataclass(DeadLetterRecord, dict(payload))
            self._records[(record.tenant_id, record.job_id)] = record

    def _flush(self) -> None:
        atomic_write_json(self._path, {"records": [to_jsonable(item) for item in self._records.values()]})


def build_default_job_dead_letter_store() -> JobDeadLetterStore:
    mode = os.getenv("BUSINESAIOS_JOB_DEAD_LETTER_STORE_BACKEND", "file").strip().lower()
    if mode == 'memory':
        return InMemoryJobDeadLetterStore()
    return PersistentJobDeadLetterStore()


__all__ = [
    "CANON_RUNTIME_QUEUE_DEAD_LETTER_STORE",
    "DeadLetterRecord",
    "InMemoryJobDeadLetterStore",
    "PersistentJobDeadLetterStore",
    "JobDeadLetterStore",
    "build_default_job_dead_letter_store",
    "runtime_dead_letter_store_path",
]
