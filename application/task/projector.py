from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.task.facts import (
    TASK_ARTIFACT_ATTACHED,
    TASK_BLOCKED,
    TASK_CANCELLED,
    TASK_COMPENSATING,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_FACT_TYPES,
    TASK_FAILED,
    TASK_PAUSED,
    TASK_READY,
    TASK_STARTED,
    TASK_SUCCEEDED,
    TASK_WAITING,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.task import (
    DurableTask,
    DurableTaskNotFound,
    DurableTaskStatus,
    RetryPolicy,
    TimeoutPolicy,
    WaitCondition,
)

CANON_DURABLE_TASK_PROJECTOR = True


class DurableTaskHistoryInvariantViolation(RuntimeError):
    pass


class DurableTaskProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(
        self,
        *,
        tenant_id: str,
        business_id: str,
        task_id: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(
                tenant_id=str(tenant_id),
                start_ms=0,
                event_type=BUSINESS_FACT_EVENT_TYPE,
            )
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in TASK_FACT_TYPES:
                continue
            if str(event.get("source") or "") != "durable_task_registry":
                raise DurableTaskHistoryInvariantViolation(
                    "task facts must come from canonical durable task registry"
                )
            if task_id is not None and entity_id != str(task_id):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(
                        envelope.get("event_time_ms")
                        or event.get("timestamp_ms")
                        or 0
                    ),
                    "observed_at_ms": int(
                        envelope.get("observed_at_ms")
                        or event.get("timestamp_ms")
                        or 0
                    ),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(
            key=lambda row: (
                int(row["event_time_ms"]),
                int(row["observed_at_ms"]),
                int(row["append_order"]),
                str(row["fact_id"]),
            )
        )
        return rows

    @staticmethod
    def _next(task: DurableTask, *, status: DurableTaskStatus, when: int, **changes: object) -> DurableTask:
        return replace(
            task,
            status=status,
            updated_at_ms=max(task.updated_at_ms, when),
            version=task.version + 1,
            **changes,
        )

    def get(self, *, tenant_id: str, business_id: str, task_id: str) -> DurableTask:
        facts = self._facts(
            tenant_id=tenant_id,
            business_id=business_id,
            task_id=task_id,
        )
        created_rows = [row for row in facts if row["fact_type"] == TASK_CREATED]
        if not created_rows:
            raise DurableTaskNotFound(f"task not found: {task_id}")
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise DurableTaskHistoryInvariantViolation(
                "task history must begin with exactly one creation"
            )
        created = created_rows[0]
        payload = dict(created["payload"])
        task = DurableTask(
            task_id=str(task_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            title=payload.get("title"),
            status=DurableTaskStatus.CREATED,
            retry_policy=RetryPolicy.from_dict(dict(payload.get("retry_policy") or {})),
            timeout_policy=TimeoutPolicy.from_dict(dict(payload.get("timeout_policy") or {})),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
            version=1,
        )

        terminal_states = {
            DurableTaskStatus.SUCCEEDED,
            DurableTaskStatus.FAILED,
            DurableTaskStatus.CANCELLED,
        }

        for row in facts[1:]:
            fact_type = str(row["fact_type"])
            when = int(row["event_time_ms"])
            payload = dict(row["payload"])

            if task.status in terminal_states:
                raise DurableTaskHistoryInvariantViolation(
                    f"task history continues after terminal state: {task.status.value}"
                )

            if fact_type == TASK_ARTIFACT_ATTACHED:
                artifact_id = str(payload.get("artifact_id") or "").strip()
                if not artifact_id:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.artifact_attached requires artifact_id"
                    )
                if artifact_id in task.artifact_ids:
                    raise DurableTaskHistoryInvariantViolation(
                        "task history contains duplicate artifact attachment"
                    )
                task = self._next(
                    task,
                    status=task.status,
                    when=when,
                    artifact_ids=(*task.artifact_ids, artifact_id),
                )
                continue

            if fact_type == TASK_READY:
                if task.status not in {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.PAUSED,
                    DurableTaskStatus.BLOCKED,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        f"task.ready invalid from {task.status.value}"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.READY,
                    when=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_STARTED:
                # Direct CREATED -> RUNNING is retained for pre-Phase-9 history
                # and callers. New orchestration should use CREATED -> READY -> RUNNING.
                if task.status not in {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.READY,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.started requires created or ready state"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.RUNNING,
                    when=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_WAITING:
                if task.status is not DurableTaskStatus.RUNNING:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.waiting requires running state"
                    )
                raw_wait = payload.get("wait_condition")
                if not isinstance(raw_wait, dict):
                    raise DurableTaskHistoryInvariantViolation(
                        "task.waiting requires persisted wait_condition"
                    )
                try:
                    wait_condition = WaitCondition.from_dict(dict(raw_wait))
                except (TypeError, ValueError) as exc:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.waiting contains invalid wait_condition"
                    ) from exc
                task = self._next(
                    task,
                    status=DurableTaskStatus.WAITING,
                    when=when,
                    wait_condition=wait_condition,
                )
                continue

            if fact_type == TASK_PAUSED:
                if task.status not in {
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.BLOCKED,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        f"task.paused invalid from {task.status.value}"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.PAUSED,
                    when=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_BLOCKED:
                if task.status not in {
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        f"task.blocked invalid from {task.status.value}"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.BLOCKED,
                    when=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_COMPENSATING:
                if task.status not in {
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.BLOCKED,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        f"task.compensating invalid from {task.status.value}"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.COMPENSATING,
                    when=when,
                    wait_condition=None,
                )
                continue

            if fact_type in {TASK_SUCCEEDED, TASK_COMPLETED}:
                if task.status is not DurableTaskStatus.RUNNING:
                    raise DurableTaskHistoryInvariantViolation(
                        f"{fact_type} requires running state"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.SUCCEEDED,
                    when=when,
                    terminal_at_ms=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_FAILED:
                if task.status not in {
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.BLOCKED,
                    DurableTaskStatus.COMPENSATING,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.failed requires running, blocked, or compensating state"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.FAILED,
                    when=when,
                    terminal_at_ms=when,
                    wait_condition=None,
                )
                continue

            if fact_type == TASK_CANCELLED:
                if task.status not in {
                    DurableTaskStatus.CREATED,
                    DurableTaskStatus.READY,
                    DurableTaskStatus.RUNNING,
                    DurableTaskStatus.WAITING,
                    DurableTaskStatus.PAUSED,
                    DurableTaskStatus.BLOCKED,
                    DurableTaskStatus.COMPENSATING,
                }:
                    raise DurableTaskHistoryInvariantViolation(
                        f"task.cancelled invalid from {task.status.value}"
                    )
                task = self._next(
                    task,
                    status=DurableTaskStatus.CANCELLED,
                    when=when,
                    terminal_at_ms=when,
                    wait_condition=None,
                )
                continue

            raise DurableTaskHistoryInvariantViolation(
                f"unknown task fact type: {fact_type}"
            )

        return task

    def list_for_business(
        self,
        *,
        tenant_id: str,
        business_id: str,
    ) -> tuple[DurableTask, ...]:
        ids = sorted(
            {
                str(row["entity_id"])
                for row in self._facts(
                    tenant_id=tenant_id,
                    business_id=business_id,
                )
            }
        )
        return tuple(
            self.get(
                tenant_id=tenant_id,
                business_id=business_id,
                task_id=value,
            )
            for value in ids
        )


__all__ = [
    "CANON_DURABLE_TASK_PROJECTOR",
    "DurableTaskHistoryInvariantViolation",
    "DurableTaskProjector",
]
