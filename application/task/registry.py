from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.task.facts import (
    TASK_ARTIFACT_ATTACHED,
    TASK_BLOCKED,
    TASK_CANCELLED,
    TASK_COMPENSATING,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_FAILED,
    TASK_PAUSED,
    TASK_PREEMPTION_REQUESTED,
    TASK_READY,
    TASK_STARTED,
    TASK_SUCCEEDED,
    TASK_WAITING,
)
from application.task.projector import DurableTaskProjector
from contracts.task import DurableTask, DurableTaskStatus, RetryPolicy, TimeoutPolicy, WaitCondition
from reliability.distributed_lock import DistributedLock, LockLease
from reliability.idempotency_contract import IdempotencyStore

CANON_DURABLE_TASK_LIFECYCLE_OWNER = True


class DurableTaskRegistry:
    def __init__(
        self,
        *,
        event_store: Any,
        idempotency_store: IdempotencyStore,
        artifact_registry: Any | None = None,
    ) -> None:
        self._projector = DurableTaskProjector(event_store)
        self._artifact_registry = artifact_registry
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="task_fact",
            source="durable_task_registry",
            id_prefix="task",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        when = int(time.time() * 1000) if value is None else int(value)
        if when < 0:
            raise ValueError("task timestamp cannot be negative")
        return when

    @staticmethod
    def _state_token(task: DurableTask) -> str:
        return f"{task.version}:{task.status.value}:{task.updated_at_ms}"

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        goal_id: str | None = None,
        title: str | None = None,
        priority: int = 50,
        conflict_keys: tuple[str, ...] = (),
        retry_policy: RetryPolicy | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> DurableTask:
        when = self._time(occurred_at_ms)
        candidate = DurableTask(
            task_id=task_id,
            tenant_id=tenant_id,
            business_id=business_id,
            goal_id=goal_id,
            title=title,
            priority=priority,
            conflict_keys=conflict_keys,
            retry_policy=retry_policy or RetryPolicy(),
            timeout_policy=timeout_policy or TimeoutPolicy(),
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = {
            "goal_id": candidate.goal_id,
            "title": candidate.title,
            "priority": candidate.priority,
            "conflict_keys": list(candidate.conflict_keys),
            "retry_policy": candidate.retry_policy.to_dict(),
            "timeout_policy": candidate.timeout_policy.to_dict(),
        }
        try:
            current = self._projector.get(
                tenant_id=tenant_id,
                business_id=business_id,
                task_id=task_id,
            )
        except LookupError:
            current = None
        if current is not None:
            if (
                current.goal_id != candidate.goal_id
                or current.title != candidate.title
                or current.priority != candidate.priority
                or current.conflict_keys != candidate.conflict_keys
                or current.retry_policy != candidate.retry_policy
                or current.timeout_policy != candidate.timeout_policy
            ):
                raise ValueError("task already exists with different identity metadata")
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=task_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=TASK_CREATED,
                payload=payload,
                event_metadata=event_metadata,
            )
            if not repaired:
                raise ValueError(
                    "task already exists and create idempotency key does not match"
                )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=task_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=TASK_CREATED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )

    def _transition(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        operation: str,
        fact_type: str,
        target_status: DurableTaskStatus,
        allowed_from: frozenset[DurableTaskStatus],
        occurred_at_ms: int | None,
        event_metadata: dict[str, object] | None,
        payload: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )
        transition_payload = dict(payload or {})
        if expected_version is not None and current.version != int(expected_version):
            raise RuntimeError(
                f"task version conflict: expected {int(expected_version)}, got {current.version}"
            )
        if current.status is target_status:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=task_id,
                operation=operation,
                idempotency_key=idempotency_key,
                fact_type=fact_type,
                payload=transition_payload,
                event_metadata=event_metadata,
            )
            if repaired:
                return current
            raise ValueError(
                f"task transition already applied with another idempotency key: {operation}"
            )
        if current.status not in allowed_from:
            raise ValueError(
                f"invalid task transition: {current.status.value} -> {operation}"
            )
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=task_id,
            expected_state_token=self._state_token(current),
            operation=operation,
            idempotency_key=idempotency_key,
            fact_type=fact_type,
            payload=transition_payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )

    def request_preemption(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        requested_by_task_id: str,
        requested_priority: int,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )
        requester = str(requested_by_task_id or "").strip()
        if not requester or requester == current.task_id:
            raise ValueError("valid requested_by_task_id is required")
        if isinstance(requested_priority, bool):
            raise ValueError("requested_priority must be an integer")
        priority = int(requested_priority)
        if current.status is not DurableTaskStatus.RUNNING:
            raise ValueError("only RUNNING task can receive preemption request")
        if priority <= current.priority or priority > 100:
            raise ValueError("preempting task must have higher priority")
        if expected_version is not None and current.version != int(expected_version):
            raise RuntimeError(
                f"task version conflict: expected {int(expected_version)}, got {current.version}"
            )
        payload = {
            "requested_by_task_id": requester,
            "requested_priority": priority,
        }
        operation = f"request_preemption:{requester}"
        if current.preemption_requested_by_task_id is not None:
            if (
                current.preemption_requested_by_task_id == requester
                and current.preemption_requested_priority == priority
                and self._writer.repair_existing(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    entity_id=task_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fact_type=TASK_PREEMPTION_REQUESTED,
                    payload=payload,
                    event_metadata=event_metadata,
                )
            ):
                return current
            raise ValueError("task preemption is already requested")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=task_id,
            expected_state_token=self._state_token(current),
            operation=operation,
            idempotency_key=idempotency_key,
            fact_type=TASK_PREEMPTION_REQUESTED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )

    def attach_artifact(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        artifact_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        current = self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )
        artifact_key = str(artifact_id or "").strip()
        if not artifact_key:
            raise ValueError("artifact_id is required")
        if expected_version is not None and current.version != int(expected_version):
            raise RuntimeError(
                f"task version conflict: expected {int(expected_version)}, got {current.version}"
            )
        payload = {"artifact_id": artifact_key}
        operation = f"attach_artifact:{artifact_key}"
        if artifact_key in current.artifact_ids:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=task_id,
                operation=operation,
                idempotency_key=idempotency_key,
                fact_type=TASK_ARTIFACT_ATTACHED,
                payload=payload,
                event_metadata=event_metadata,
            )
            if repaired:
                return current
            raise ValueError("artifact already attached with another idempotency key")
        if current.status in {
            DurableTaskStatus.SUCCEEDED,
            DurableTaskStatus.FAILED,
            DurableTaskStatus.CANCELLED,
        }:
            raise ValueError("cannot attach artifact to terminal task")
        if self._artifact_registry is None:
            raise RuntimeError("artifact registry is not configured")
        artifact = self._artifact_registry.get(
            tenant_id=tenant_id,
            business_id=business_id,
            artifact_id=artifact_key,
        )
        if str(getattr(artifact, "artifact_id", "") or "") != artifact_key:
            raise RuntimeError("artifact registry returned mismatched identity")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=task_id,
            expected_state_token=self._state_token(current),
            operation=operation,
            idempotency_key=idempotency_key,
            fact_type=TASK_ARTIFACT_ATTACHED,
            payload=payload,
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )

    def ready(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="ready",
            fact_type=TASK_READY,
            target_status=DurableTaskStatus.READY,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.PAUSED,
                    DurableTaskStatus.BLOCKED,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def start(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="start",
            fact_type=TASK_STARTED,
            target_status=DurableTaskStatus.RUNNING,
            # CREATED -> RUNNING is a compatibility path for pre-Phase-9 callers.
            allowed_from=frozenset(
                {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.READY,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def wait(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        wait_condition: WaitCondition,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        if not isinstance(wait_condition, WaitCondition):
            raise TypeError("wait_condition must be WaitCondition")
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="wait",
            fact_type=TASK_WAITING,
            target_status=DurableTaskStatus.WAITING,
            allowed_from=frozenset({DurableTaskStatus.RUNNING}),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            payload={"wait_condition": wait_condition.to_dict()},
            expected_version=expected_version,
        )

    def pause(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="pause",
            fact_type=TASK_PAUSED,
            target_status=DurableTaskStatus.PAUSED,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.BLOCKED,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def block(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="block",
            fact_type=TASK_BLOCKED,
            target_status=DurableTaskStatus.BLOCKED,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def begin_compensation(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="begin_compensation",
            fact_type=TASK_COMPENSATING,
            target_status=DurableTaskStatus.COMPENSATING,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.BLOCKED,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def succeed(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="succeed",
            fact_type=TASK_SUCCEEDED,
            target_status=DurableTaskStatus.SUCCEEDED,
            allowed_from=frozenset({DurableTaskStatus.RUNNING}),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def complete(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        """Backward-compatible success transition for pre-Phase-9 callers."""
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="complete",
            fact_type=TASK_COMPLETED,
            target_status=DurableTaskStatus.SUCCEEDED,
            allowed_from=frozenset({DurableTaskStatus.RUNNING}),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def fail(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="fail",
            fact_type=TASK_FAILED,
            target_status=DurableTaskStatus.FAILED,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.BLOCKED,
                    DurableTaskStatus.COMPENSATING,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def cancel(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
        expected_version: int | None = None,
    ) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            operation="cancel",
            fact_type=TASK_CANCELLED,
            target_status=DurableTaskStatus.CANCELLED,
            allowed_from=frozenset(
                {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.PAUSED,
                    DurableTaskStatus.BLOCKED,
                    DurableTaskStatus.COMPENSATING,
                }
            ),
            occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
            expected_version=expected_version,
        )

    def get(self, *, tenant_id: str, business_id: str, task_id: str) -> DurableTask:
        return self._projector.get(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
    ) -> tuple[DurableTask, ...]:
        return self._projector.list_for_business(
            tenant_id=tenant_id,
            business_id=business_id,
        )



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


class TaskConflictLeaseHeartbeat:
    def __init__(
        self,
        *,
        controller: "TaskConflictController",
        group: TaskConflictLeaseGroup,
        ttl_seconds: int,
        interval_seconds: float,
    ) -> None:
        self._controller = controller
        self._group = group
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._interval_seconds = max(0.01, float(interval_seconds))
        self._stop = Event()
        self._guard = Lock()
        self._error: BaseException | None = None
        self._thread = Thread(target=self._run, name=f"task-conflict-heartbeat-{group.task_id}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                renewed = self._controller.renew(
                    self._group,
                    ttl_seconds=self._ttl_seconds,
                )
            except BaseException as exc:
                with self._guard:
                    self._error = exc
                self._stop.set()
                return
            with self._guard:
                self._group = renewed

    def close(self) -> TaskConflictLeaseGroup:
        self._stop.set()
        self._thread.join(timeout=max(1.0, self._interval_seconds + 1.0))
        with self._guard:
            if self._error is not None:
                raise RuntimeError("durable task conflict lease renewal failed") from self._error
            return self._group


class TaskQueuePreemptionCoordinator:
    """Cooperative admission over the canonical Task registry and lock owner."""

    def __init__(
        self,
        *,
        task_registry: DurableTaskRegistry,
        distributed_lock: DistributedLock,
    ) -> None:
        self._tasks = task_registry
        self._lock = distributed_lock

    @staticmethod
    def _owner_id(*, business_id: str, task_id: str) -> str:
        return f"durable-task:{str(business_id).strip()}:{str(task_id).strip()}"

    def admit(self, job: Any) -> bool:
        tags = tuple(str(tag) for tag in (getattr(job, "tags", ()) or ()))
        if "durable_task" not in tags:
            return True
        payload = dict(getattr(job, "payload", {}) or {})
        task_id = str(payload.get("task_id") or "").strip()
        business_id = str(payload.get("business_id") or "").strip()
        raw_keys = payload.get("task_conflict_keys")
        if not task_id or not business_id or not isinstance(raw_keys, list):
            return False
        candidate = self._tasks.get(
            tenant_id=job.tenant_id,
            business_id=business_id,
            task_id=task_id,
        )
        if candidate.status is not DurableTaskStatus.READY:
            return False
        try:
            payload_priority = int(payload.get("task_priority"))
        except (TypeError, ValueError):
            return False
        conflict_keys = tuple(
            sorted(dict.fromkeys(_normalize_conflict_key(key) for key in raw_keys))
        )
        canonical_keys = tuple(sorted(candidate.conflict_keys))
        if (
            payload_priority != candidate.priority
            or int(getattr(job, "priority", -1)) != candidate.priority
            or conflict_keys != canonical_keys
        ):
            return False
        if not conflict_keys:
            return True
        blocked = False
        tasks = self._tasks.list_for_business(
            tenant_id=job.tenant_id,
            business_id=business_id,
        )
        for key in conflict_keys:
            resource = TaskConflictController._resource(
                business_id=business_id,
                conflict_key=key,
            )
            lease = self._lock.get(tenant_id=job.tenant_id, resource=resource)
            if lease is None:
                continue
            blocked = True
            target = next(
                (
                    task
                    for task in tasks
                    if task.status is DurableTaskStatus.RUNNING
                    and key in task.conflict_keys
                    and lease.owner_id
                    == self._owner_id(
                        business_id=business_id,
                        task_id=task.task_id,
                    )
                ),
                None,
            )
            if target is None or candidate.priority <= target.priority:
                continue
            if target.preemption_requested_by_task_id is not None:
                continue
            try:
                self._tasks.request_preemption(
                    tenant_id=job.tenant_id,
                    business_id=business_id,
                    task_id=target.task_id,
                    requested_by_task_id=candidate.task_id,
                    requested_priority=candidate.priority,
                    idempotency_key=(
                        f"queue-preempt:{target.task_id}:by:{candidate.task_id}"
                    ),
                    expected_version=target.version,
                )
            except RuntimeError as exc:
                if "task version conflict" not in str(exc):
                    raise
                refreshed = self._tasks.get(
                    tenant_id=job.tenant_id,
                    business_id=business_id,
                    task_id=target.task_id,
                )
                if (
                    refreshed.status is DurableTaskStatus.RUNNING
                    and refreshed.preemption_requested_by_task_id is None
                ):
                    return False
        return not blocked


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

    def renew(
        self,
        group: TaskConflictLeaseGroup,
        *,
        ttl_seconds: int = 3600,
    ) -> TaskConflictLeaseGroup:
        renewed: list[LockLease] = []
        try:
            for lease in group.leases:
                renewed.append(
                    self._lock.renew(
                        lease=lease,
                        ttl_seconds=ttl_seconds,
                    )
                )
        except BaseException:
            for lease in reversed(tuple(renewed) + group.leases[len(renewed):]):
                self._lock.release(lease=lease)
            raise
        return TaskConflictLeaseGroup(
            tenant_id=group.tenant_id,
            business_id=group.business_id,
            task_id=group.task_id,
            leases=tuple(renewed),
        )

    def heartbeat(
        self,
        group: TaskConflictLeaseGroup,
        *,
        ttl_seconds: int = 3600,
        interval_seconds: float | None = None,
    ) -> TaskConflictLeaseHeartbeat:
        interval = (
            max(1.0, float(ttl_seconds) / 3.0)
            if interval_seconds is None
            else float(interval_seconds)
        )
        return TaskConflictLeaseHeartbeat(
            controller=self,
            group=group,
            ttl_seconds=ttl_seconds,
            interval_seconds=interval,
        )

    def release(self, group: TaskConflictLeaseGroup) -> None:
        for lease in reversed(group.leases):
            self._lock.release(lease=lease)



__all__ = [
    "CANON_DURABLE_TASK_CONFLICT_CONTROL",
    "CANON_DURABLE_TASK_LIFECYCLE_OWNER",
    "DurableTaskRegistry",
    "TaskConflictController",
    "TaskConflictLeaseGroup",
    "TaskConflictLeaseHeartbeat",
    "TaskQueuePreemptionCoordinator",
]
