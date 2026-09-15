from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.task.facts import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_FACT_TYPES,
    TASK_FAILED,
    TASK_STARTED,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.task import DurableTask, DurableTaskNotFound, DurableTaskStatus

CANON_DURABLE_TASK_PROJECTOR = True


class DurableTaskHistoryInvariantViolation(RuntimeError):
    pass


class DurableTaskProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, task_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type, entity_id = str(envelope.get("fact_type") or ""), str(envelope.get("entity_id") or "")
            if fact_type not in TASK_FACT_TYPES or (task_id is not None and entity_id != str(task_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""), "fact_type": fact_type, "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order, "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, task_id: str) -> DurableTask:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, task_id=task_id)
        created = next((row for row in facts if row["fact_type"] == TASK_CREATED), None)
        if created is None:
            raise DurableTaskNotFound(f"task not found: {task_id}")
        payload = dict(created["payload"])
        task = DurableTask(
            task_id=str(task_id), tenant_id=str(tenant_id), business_id=str(business_id),
            title=payload.get("title"), created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row is created:
                continue
            fact_type = row["fact_type"]
            when = int(row["event_time_ms"])
            if task.status in {
                DurableTaskStatus.COMPLETED,
                DurableTaskStatus.FAILED,
                DurableTaskStatus.CANCELLED,
            }:
                raise DurableTaskHistoryInvariantViolation(
                    f"task history continues after terminal state: {task.status.value}"
                )
            if fact_type == TASK_STARTED:
                if task.status is not DurableTaskStatus.PENDING:
                    raise DurableTaskHistoryInvariantViolation("task.started requires pending state")
                task = replace(
                    task, status=DurableTaskStatus.RUNNING,
                    updated_at_ms=max(task.updated_at_ms, when),
                )
            elif fact_type in {TASK_COMPLETED, TASK_FAILED}:
                if task.status is not DurableTaskStatus.RUNNING:
                    raise DurableTaskHistoryInvariantViolation(
                        f"{fact_type} requires running state"
                    )
                status = (
                    DurableTaskStatus.COMPLETED
                    if fact_type == TASK_COMPLETED
                    else DurableTaskStatus.FAILED
                )
                task = replace(
                    task, status=status, updated_at_ms=max(task.updated_at_ms, when),
                    terminal_at_ms=when,
                )
            elif fact_type == TASK_CANCELLED:
                if task.status not in {DurableTaskStatus.PENDING, DurableTaskStatus.RUNNING}:
                    raise DurableTaskHistoryInvariantViolation(
                        "task.cancelled requires pending or running state"
                    )
                task = replace(
                    task, status=DurableTaskStatus.CANCELLED,
                    updated_at_ms=max(task.updated_at_ms, when), terminal_at_ms=when,
                )
        return task

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[DurableTask, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, task_id=value) for value in ids)


__all__ = [
    "CANON_DURABLE_TASK_PROJECTOR",
    "DurableTaskHistoryInvariantViolation",
    "DurableTaskProjector",
]
