from __future__ import annotations

import threading

import pytest

from application.task import (
    DurableTaskHistoryInvariantViolation,
    DurableTaskProjector,
    DurableTaskRegistry,
)
from contracts.event_store import BusinessFactV1
from contracts.task import DurableTaskNotFound, DurableTaskStatus
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(
        self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None
    ):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)

    def count_events(
        self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None
    ) -> int:
        return sum(
            1
            for _ in self.iter_events(
                tenant_id=tenant_id,
                start_ms=start_ms,
                end_ms=end_ms,
                user_id=user_id,
                event_type=event_type,
            )
        )


def _registry() -> tuple[DurableTaskRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return DurableTaskRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    ), events


def test_task_lifecycle_and_exact_transition_replay_are_durable() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
        idempotency_key="create-a",
        title="Prepare proposal",
        occurred_at_ms=100,
    )
    assert created.status is DurableTaskStatus.PENDING

    running = registry.start(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
        idempotency_key="start-a",
        occurred_at_ms=200,
    )
    assert running.status is DurableTaskStatus.RUNNING
    replay_running = registry.start(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
        idempotency_key="start-a",
        occurred_at_ms=999,
    )
    assert replay_running == running

    completed = registry.complete(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
        idempotency_key="complete-a",
        occurred_at_ms=300,
    )
    assert completed.status is DurableTaskStatus.COMPLETED
    assert completed.terminal_at_ms == 300
    replay_completed = registry.complete(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
        idempotency_key="complete-a",
        occurred_at_ms=1000,
    )
    assert replay_completed == completed
    assert len(events.events) == 3


def test_task_rejects_new_key_for_already_applied_transition() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="create-a", occurred_at_ms=100,
    )
    registry.start(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="start-a", occurred_at_ms=200,
    )
    with pytest.raises(ValueError, match="another idempotency key"):
        registry.start(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a",
            idempotency_key="start-b", occurred_at_ms=300,
        )


def test_task_rejects_duplicate_create_with_new_key() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="create-a", title="One", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="create idempotency key"):
        registry.create(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a",
            idempotency_key="create-b", title="One", occurred_at_ms=200,
        )
    assert len(events.events) == 1


def test_task_state_machine_rejects_invalid_transitions() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="create-a", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="pending -> complete"):
        registry.complete(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a",
            idempotency_key="complete-a", occurred_at_ms=200,
        )
    registry.cancel(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="cancel-a", occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="cancelled -> start"):
        registry.start(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a",
            idempotency_key="start-a", occurred_at_ms=400,
        )


def test_task_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = DurableTaskRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-a", business_id="business-a", task_id="shared",
        idempotency_key="a", title="A", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-b", business_id="business-b", task_id="shared",
        idempotency_key="b", title="B", occurred_at_ms=100,
    )
    projector = DurableTaskProjector(events)
    assert projector.get(
        tenant_id="tenant-a", business_id="business-a", task_id="shared"
    ).title == "A"
    assert projector.get(
        tenant_id="tenant-b", business_id="business-b", task_id="shared"
    ).title == "B"
    with pytest.raises(DurableTaskNotFound):
        projector.get(tenant_id="tenant-a", business_id="business-b", task_id="shared")


def test_competing_terminal_transitions_from_same_version_are_serialized() -> None:
    class BlockingEventStore(MemoryEventStore):
        def __init__(self) -> None:
            super().__init__()
            self.terminal_entered = threading.Event()
            self.release_terminal = threading.Event()

        def append_event(self, event: dict) -> None:
            payload = dict(event.get("payload") or {})
            if str(payload.get("fact_type") or "") == "task.completed":
                self.terminal_entered.set()
                assert self.release_terminal.wait(timeout=5)
            super().append_event(event)

    events = BlockingEventStore()
    registry = DurableTaskRegistry(
        event_store=events, idempotency_store=InMemoryIdempotencyStore()
    )
    registry.create(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="create", occurred_at_ms=100,
    )
    registry.start(
        tenant_id="tenant-a", business_id="business-a", task_id="task-a",
        idempotency_key="start", occurred_at_ms=200,
    )

    errors: list[BaseException] = []

    def complete() -> None:
        try:
            registry.complete(
                tenant_id="tenant-a", business_id="business-a", task_id="task-a",
                idempotency_key="complete", occurred_at_ms=300,
            )
        except BaseException as exc:  # pragma: no cover - assertion below exposes it
            errors.append(exc)

    worker = threading.Thread(target=complete)
    worker.start()
    assert events.terminal_entered.wait(timeout=5)
    with pytest.raises(RuntimeError, match="rejected_scope_mismatch"):
        registry.fail(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a",
            idempotency_key="fail", occurred_at_ms=301,
        )
    events.release_terminal.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert errors == []
    final = registry.get(tenant_id="tenant-a", business_id="business-a", task_id="task-a")
    assert final.status is DurableTaskStatus.COMPLETED
    terminal_facts = [
        event for event in events.events
        if str(dict(event.get("payload") or {}).get("fact_type") or "").startswith("task.")
        and str(dict(event.get("payload") or {}).get("fact_type") or "")
        in {"task.completed", "task.failed", "task.cancelled"}
    ]
    assert len(terminal_facts) == 1


def test_task_projector_fails_closed_on_invalid_persisted_history() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="task:create", tenant_id="tenant-a", business_id="business-a",
        fact_type="task.created", entity_id="task-a", event_time_ms=100,
        observed_at_ms=100, source="durable_task_registry", payload={"title": None},
    ).as_event())
    events.append_event(BusinessFactV1(
        fact_id="task:complete", tenant_id="tenant-a", business_id="business-a",
        fact_type="task.completed", entity_id="task-a", event_time_ms=200,
        observed_at_ms=200, source="durable_task_registry", payload={},
    ).as_event())
    with pytest.raises(DurableTaskHistoryInvariantViolation, match="requires running"):
        DurableTaskProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a"
        )


def test_task_projector_rejects_events_after_terminal_state() -> None:
    events = MemoryEventStore()
    for fact_id, fact_type, when in (
        ("task:create", "task.created", 100),
        ("task:start", "task.started", 200),
        ("task:complete", "task.completed", 300),
        ("task:late-fail", "task.failed", 400),
    ):
        events.append_event(BusinessFactV1(
            fact_id=fact_id, tenant_id="tenant-a", business_id="business-a",
            fact_type=fact_type, entity_id="task-a", event_time_ms=when,
            observed_at_ms=when, source="durable_task_registry",
            payload={"title": None} if fact_type == "task.created" else {},
        ).as_event())
    with pytest.raises(DurableTaskHistoryInvariantViolation, match="after terminal"):
        DurableTaskProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", task_id="task-a"
        )
