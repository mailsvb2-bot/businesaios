from __future__ import annotations

"""Execution checkpoints for crash-safe single-path runtime flow."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
import json
import threading

from core.tenancy.normalization import require_tenant_id


CANON_EXECUTION_CHECKPOINT_STORE = True
CANON_CHECKPOINT_STAGE_ORDER = (
    "request",
    "world_state",
    "decision",
    "executable_action",
    "execution",
    "verification",
    "state_update",
    "evidence",
    "completed",
    "failed",
)
_STAGE_INDEX = {name: index for index, name in enumerate(CANON_CHECKPOINT_STAGE_ORDER)}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ExecutionCheckpoint:
    tenant_id: str
    run_id: str
    sequence_no: int
    stage: str
    checkpoint_id: str
    created_at: datetime = field(default_factory=utc_now)
    trace_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    idempotency_key: str | None = None
    outbox_message_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.run_id or "").strip():
            raise ValueError("run_id is required")
        if int(self.sequence_no) < 0:
            raise ValueError("sequence_no must be >= 0")
        if not str(self.stage or "").strip():
            raise ValueError("stage is required")
        if not str(self.checkpoint_id or "").strip():
            raise ValueError("checkpoint_id is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    def to_row(self) -> dict[str, Any]:
        self.validate()
        row = asdict(self)
        row["created_at"] = self.created_at.isoformat()
        row["payload"] = dict(self.payload)
        return row

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ExecutionCheckpoint":
        created_at = datetime.fromisoformat(str(row["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        checkpoint = cls(
            tenant_id=str(row["tenant_id"]),
            run_id=str(row["run_id"]),
            sequence_no=int(row["sequence_no"]),
            stage=str(row["stage"]),
            checkpoint_id=str(row["checkpoint_id"]),
            created_at=created_at,
            trace_id=row.get("trace_id"),
            decision_id=row.get("decision_id"),
            action_id=row.get("action_id"),
            idempotency_key=row.get("idempotency_key"),
            outbox_message_id=row.get("outbox_message_id"),
            payload=dict(row.get("payload") or {}),
        )
        checkpoint.validate()
        return checkpoint


class ExecutionCheckpointStore(Protocol):
    def append(self, checkpoint: ExecutionCheckpoint) -> None: ...
    def latest(self, *, tenant_id: str, run_id: str) -> ExecutionCheckpoint | None: ...
    def list_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionCheckpoint, ...]: ...


class InMemoryExecutionCheckpointStore(ExecutionCheckpointStore):
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], list[ExecutionCheckpoint]] = {}
        self._lock = threading.RLock()

    def append(self, checkpoint: ExecutionCheckpoint) -> None:
        checkpoint.validate()
        cache_key = (checkpoint.tenant_id, checkpoint.run_id)
        with self._lock:
            items = self._items.setdefault(cache_key, [])
            if items:
                latest = items[-1]
                if checkpoint.sequence_no <= latest.sequence_no:
                    raise ValueError("checkpoint sequence_no must strictly increase")
                if checkpoint.checkpoint_id == latest.checkpoint_id:
                    raise ValueError("checkpoint_id must be unique within run")
                current_index = _STAGE_INDEX.get(str(latest.stage))
                new_index = _STAGE_INDEX.get(str(checkpoint.stage))
                if current_index is not None and new_index is not None and latest.stage != "failed":
                    if new_index < current_index and checkpoint.stage != "failed":
                        raise ValueError("checkpoint stage order must not move backwards")
            items.append(checkpoint)

    def latest(self, *, tenant_id: str, run_id: str) -> ExecutionCheckpoint | None:
        with self._lock:
            items = self._items.get((require_tenant_id(tenant_id), str(run_id)), [])
            return items[-1] if items else None

    def list_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionCheckpoint, ...]:
        with self._lock:
            return tuple(self._items.get((require_tenant_id(tenant_id), str(run_id)), []))


class JsonlExecutionCheckpointStore(ExecutionCheckpointStore):
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = InMemoryExecutionCheckpointStore()
        self._lock = threading.RLock()
        if self._path.exists():
            for raw_line in self._path.read_text(encoding="utf-8").splitlines():
                if not raw_line.strip():
                    continue
                row = json.loads(raw_line)
                self._cache.append(ExecutionCheckpoint.from_row(row))

    def append(self, checkpoint: ExecutionCheckpoint) -> None:
        with self._lock:
            self._cache.append(checkpoint)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(checkpoint.to_row(), ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()

    def latest(self, *, tenant_id: str, run_id: str) -> ExecutionCheckpoint | None:
        return self._cache.latest(tenant_id=tenant_id, run_id=run_id)

    def list_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionCheckpoint, ...]:
        return self._cache.list_run(tenant_id=tenant_id, run_id=run_id)


__all__ = [
    "CANON_CHECKPOINT_STAGE_ORDER",
    "CANON_EXECUTION_CHECKPOINT_STORE",
    "ExecutionCheckpoint",
    "ExecutionCheckpointStore",
    "InMemoryExecutionCheckpointStore",
    "JsonlExecutionCheckpointStore",
    "utc_now",
]
