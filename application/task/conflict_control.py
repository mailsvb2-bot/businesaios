from __future__ import annotations

from dataclasses import dataclass

from reliability.distributed_lock import DistributedLock, LockLease

CANON_DURABLE_TASK_CONFLICT_CONTROL = True


def _normalize_conflict_key(value: object) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 200 or any(ord(ch) < 32 for ch in text):
        raise ValueError("invalid task conflict key")
    return text


@dataclass(frozen=True, slots=True)
class TaskConflictLeaseGroup:
    tenant_id: str
    business_id: str
    task_id: str
    leases: tuple[LockLease, ...]


class TaskConflictController:
    """Task conflict adapter over the canonical distributed-lock owner."""

    def __init__(self, *, distributed_lock: DistributedLock) -> None:
        self._lock = distributed_lock

    @staticmethod
    def _resource(*, business_id: str, conflict_key: str) -> str:
        business = str(business_id or "").strip()
        if not business:
            raise ValueError("business_id is required")
        key = _normalize_conflict_key(conflict_key)
        return f"durable-task-conflict:{business}:{key}"

    def acquire(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        conflict_keys: tuple[str, ...],
        ttl_seconds: int = 3600,
    ) -> TaskConflictLeaseGroup:
        owner_id = f"durable-task:{str(business_id or '').strip()}:{str(task_id or '').strip()}"
        if owner_id.endswith(":"):
            raise ValueError("task_id is required")
        keys = tuple(sorted(dict.fromkeys(_normalize_conflict_key(key) for key in conflict_keys)))
        leases: list[LockLease] = []
        try:
            for key in keys:
                lease = self._lock.acquire(
                    tenant_id=tenant_id,
                    resource=self._resource(business_id=business_id, conflict_key=key),
                    owner_id=owner_id,
                    ttl_seconds=ttl_seconds,
                )
                if lease is None:
                    raise RuntimeError(f"durable task conflict is already locked: {key}")
                leases.append(lease)
        except Exception:
            for lease in reversed(leases):
                self._lock.release(lease=lease)
            raise
        return TaskConflictLeaseGroup(
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            task_id=str(task_id),
            leases=tuple(leases),
        )

    def release(self, group: TaskConflictLeaseGroup) -> None:
        for lease in reversed(group.leases):
            self._lock.release(lease=lease)


__all__ = [
    "CANON_DURABLE_TASK_CONFLICT_CONTROL",
    "TaskConflictController",
    "TaskConflictLeaseGroup",
]
