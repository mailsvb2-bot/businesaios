from __future__ import annotations

import time
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.task.facts import TASK_CANCELLED, TASK_COMPLETED, TASK_CREATED, TASK_FAILED, TASK_STARTED
from application.task.projector import DurableTaskProjector
from contracts.task import DurableTask, DurableTaskStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_DURABLE_TASK_LIFECYCLE_OWNER = True


class DurableTaskRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = DurableTaskProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="task_fact", source="durable_task_registry", id_prefix="task",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def create(self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str, title: str | None = None, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> DurableTask:
        when = self._time(occurred_at_ms)
        candidate = DurableTask(task_id=task_id, tenant_id=tenant_id, business_id=business_id, title=title, created_at_ms=when, updated_at_ms=when)
        payload = {"title": candidate.title}
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)
        except LookupError:
            current = None
        if current is not None:
            if current.title != candidate.title:
                raise ValueError("task already exists with different identity metadata")
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=task_id,
                operation="create", idempotency_key=idempotency_key, fact_type=TASK_CREATED, payload=payload,
                event_metadata=event_metadata,
            )
            if not repaired:
                raise ValueError("task already exists and create idempotency key does not match")
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=task_id,
            operation="create", idempotency_key=idempotency_key, fact_type=TASK_CREATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)

    def _transition(
        self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str,
        operation: str, fact_type: str, target_status: DurableTaskStatus,
        allowed_from: frozenset[DurableTaskStatus], occurred_at_ms: int | None,
        event_metadata: dict[str, object] | None,
    ) -> DurableTask:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)
        if current.status is target_status:
            repaired = self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=task_id,
                operation=operation, idempotency_key=idempotency_key, fact_type=fact_type, payload={},
                event_metadata=event_metadata,
            )
            if repaired:
                return current
            raise ValueError(f"task transition already applied with another idempotency key: {operation}")
        if current.status not in allowed_from:
            raise ValueError(f"invalid task transition: {current.status.value} -> {operation}")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        state_token = f"{current.status.value}:{current.updated_at_ms}"
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=task_id,
            expected_state_token=state_token, operation=operation,
            idempotency_key=idempotency_key, fact_type=fact_type, payload={}, occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)

    def start(self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id, business_id=business_id, task_id=task_id, idempotency_key=idempotency_key,
            operation="start", fact_type=TASK_STARTED, target_status=DurableTaskStatus.RUNNING, allowed_from=frozenset({DurableTaskStatus.PENDING}), occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
        )

    def complete(self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id, business_id=business_id, task_id=task_id, idempotency_key=idempotency_key,
            operation="complete", fact_type=TASK_COMPLETED, target_status=DurableTaskStatus.COMPLETED, allowed_from=frozenset({DurableTaskStatus.RUNNING}), occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
        )

    def fail(self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id, business_id=business_id, task_id=task_id, idempotency_key=idempotency_key,
            operation="fail", fact_type=TASK_FAILED, target_status=DurableTaskStatus.FAILED, allowed_from=frozenset({DurableTaskStatus.RUNNING}), occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
        )

    def cancel(self, *, tenant_id: str, business_id: str, task_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> DurableTask:
        return self._transition(
            tenant_id=tenant_id, business_id=business_id, task_id=task_id, idempotency_key=idempotency_key,
            operation="cancel", fact_type=TASK_CANCELLED, target_status=DurableTaskStatus.CANCELLED,
            allowed_from=frozenset({DurableTaskStatus.PENDING, DurableTaskStatus.RUNNING}), occurred_at_ms=occurred_at_ms,
            event_metadata=event_metadata,
        )

    def get(self, *, tenant_id: str, business_id: str, task_id: str) -> DurableTask:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, task_id=task_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[DurableTask, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_DURABLE_TASK_LIFECYCLE_OWNER", "DurableTaskRegistry"]
