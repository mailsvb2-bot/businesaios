from __future__ import annotations

import time
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
    TASK_READY,
    TASK_STARTED,
    TASK_SUCCEEDED,
    TASK_WAITING,
)
from application.task.projector import DurableTaskProjector
from contracts.task import DurableTask, DurableTaskStatus, RetryPolicy, TimeoutPolicy, WaitCondition
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
        title: str | None = None,
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
            title=title,
            retry_policy=retry_policy or RetryPolicy(),
            timeout_policy=timeout_policy or TimeoutPolicy(),
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = {
            "title": candidate.title,
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
                current.title != candidate.title
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


__all__ = ["CANON_DURABLE_TASK_LIFECYCLE_OWNER", "DurableTaskRegistry"]
