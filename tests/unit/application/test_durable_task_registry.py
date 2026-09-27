from __future__ import annotations

import threading

import pytest

from application.artifact import ArtifactRegistry
from application.task import (
    DurableTaskHistoryInvariantViolation,
    DurableTaskProjector,
    DurableTaskRegistry,
)
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
from contracts.task import (
    DurableTask,
    DurableTaskNotFound,
    DurableTaskStatus,
    RetryPolicy,
    TimeoutPolicy,
    WaitCondition,
    WaitConditionKind,
)
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


def test_task_metadata_propagates_and_exact_replay_rejects_change() -> None:
    registry, events = _registry()
    create_metadata = { "actor_id": "owner-1", "decision_id": "decision-create", "evidence_ids": ("task-evidence-1",), }
    created = registry.create( tenant_id="t", business_id="b", task_id="task", idempotency_key="create-meta", title="Ship", occurred_at_ms=100, event_metadata=create_metadata, )
    assert registry.create( tenant_id="t", business_id="b", task_id="task", idempotency_key="create-meta", title="Ship", occurred_at_ms=999, event_metadata=create_metadata, ) == created
    assert canonical_business_event_contract(events.events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        registry.create( tenant_id="t", business_id="b", task_id="task", idempotency_key="create-meta", title="Ship", occurred_at_ms=100, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    start_metadata = {"actor_id": "owner-1", "decision_id": "decision-start"}
    running = registry.start( tenant_id="t", business_id="b", task_id="task", idempotency_key="start-meta", occurred_at_ms=200, event_metadata=start_metadata, )
    assert registry.start( tenant_id="t", business_id="b", task_id="task", idempotency_key="start-meta", occurred_at_ms=999, event_metadata=start_metadata, ) == running
    with pytest.raises(ValueError, match="event metadata"):
        registry.start( tenant_id="t", business_id="b", task_id="task", idempotency_key="start-meta", occurred_at_ms=200, event_metadata={**start_metadata, "actor_id": "owner-2"}, )
    complete_metadata = {"actor_id": "owner-1", "decision_id": "decision-complete"}
    completed = registry.complete( tenant_id="t", business_id="b", task_id="task", idempotency_key="complete-meta", occurred_at_ms=300, event_metadata=complete_metadata, )
    assert registry.complete( tenant_id="t", business_id="b", task_id="task", idempotency_key="complete-meta", occurred_at_ms=999, event_metadata=complete_metadata, ) == completed
    with pytest.raises(ValueError, match="event metadata"):
        registry.complete( tenant_id="t", business_id="b", task_id="task", idempotency_key="complete-meta", occurred_at_ms=300, event_metadata={**complete_metadata, "actor_id": "owner-2"}, )


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
    with pytest.raises(ValueError, match="created -> complete"):
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



def test_phase9_canonical_ready_wait_resume_survives_runtime_reconstruction() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = DurableTaskRegistry(event_store=events, idempotency_store=claims)

    created = registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="create",
        title="Wait for approval",
        occurred_at_ms=100,
    )
    assert created.status is DurableTaskStatus.CREATED
    assert created.version == 1

    ready = registry.ready(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="ready",
        expected_version=1,
        occurred_at_ms=110,
    )
    assert ready.status is DurableTaskStatus.READY
    assert ready.version == 2

    running = registry.start(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="start",
        expected_version=2,
        occurred_at_ms=120,
    )
    wait_condition = WaitCondition(
        condition_id="approval-owner",
        kind=WaitConditionKind.APPROVAL,
        correlation_key="approval:task-p9",
    )
    waiting = registry.wait(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="wait",
        wait_condition=wait_condition,
        expected_version=running.version,
        occurred_at_ms=130,
    )
    assert waiting.status is DurableTaskStatus.WAITING
    assert waiting.wait_condition == wait_condition

    reconstructed = DurableTaskRegistry(
        event_store=events,
        idempotency_store=claims,
    ).get(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
    )
    assert reconstructed == waiting

    resumed = registry.ready(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="resume",
        expected_version=waiting.version,
        occurred_at_ms=140,
    )
    assert resumed.status is DurableTaskStatus.READY
    assert resumed.wait_condition is None
    assert resumed.version == waiting.version + 1


def test_phase9_stale_version_fails_closed_without_new_event() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="create",
        occurred_at_ms=100,
    )
    registry.ready(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="ready",
        expected_version=1,
        occurred_at_ms=110,
    )
    before = len(events.events)
    with pytest.raises(RuntimeError, match="task version conflict"):
        registry.start(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            idempotency_key="stale-start",
            expected_version=1,
            occurred_at_ms=120,
        )
    assert len(events.events) == before


def test_phase9_date_wait_requires_durable_wakeup_time() -> None:
    with pytest.raises(ValueError, match="date wait condition requires resume_at_ms"):
        WaitCondition(
            condition_id="scheduled",
            kind=WaitConditionKind.DATE,
        )
    condition = WaitCondition(
        condition_id="scheduled",
        kind=WaitConditionKind.DATE,
        resume_at_ms=1_000,
    )
    assert WaitCondition.from_dict(condition.to_dict()) == condition


def test_phase9_compensation_is_explicit_and_not_fake_rollback() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="create",
        occurred_at_ms=100,
    )
    registry.start(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="start",
        occurred_at_ms=110,
    )
    compensating = registry.begin_compensation(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="compensate",
        occurred_at_ms=120,
    )
    assert compensating.status is DurableTaskStatus.COMPENSATING
    failed = registry.fail(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="fail-after-compensation",
        occurred_at_ms=130,
    )
    assert failed.status is DurableTaskStatus.FAILED
    assert failed.terminal_at_ms == 130



def test_phase9_task_artifact_binding_reuses_canonical_artifact_owner() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    artifacts = ArtifactRegistry(event_store=events, idempotency_store=claims)
    registry = DurableTaskRegistry(
        event_store=events,
        idempotency_store=claims,
        artifact_registry=artifacts,
    )
    artifacts.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        artifact_id="artifact-p9",
        idempotency_key="artifact-create",
        artifact_kind="execution_output",
        storage_ref="evidence://artifact-p9",
        occurred_at_ms=90,
    )
    registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="task-create",
        occurred_at_ms=100,
    )
    attached = registry.attach_artifact(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        artifact_id="artifact-p9",
        idempotency_key="attach",
        expected_version=1,
        occurred_at_ms=110,
    )
    assert attached.artifact_ids == ("artifact-p9",)
    assert attached.version == 2
    assert registry.attach_artifact(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        artifact_id="artifact-p9",
        idempotency_key="attach",
        occurred_at_ms=999,
    ) == attached


def test_phase9_task_artifact_binding_fails_closed_for_wrong_scope_and_terminal_task() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    artifacts = ArtifactRegistry(event_store=events, idempotency_store=claims)
    registry = DurableTaskRegistry(
        event_store=events,
        idempotency_store=claims,
        artifact_registry=artifacts,
    )
    artifacts.create(
        tenant_id="tenant-p9",
        business_id="other-business",
        artifact_id="artifact-other",
        idempotency_key="artifact-create",
        occurred_at_ms=90,
    )
    registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="task-create",
        occurred_at_ms=100,
    )
    before = len(events.events)
    with pytest.raises(LookupError):
        registry.attach_artifact(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            artifact_id="artifact-other",
            idempotency_key="attach-wrong-scope",
            occurred_at_ms=110,
        )
    assert len(events.events) == before

    registry.start(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="start",
        occurred_at_ms=120,
    )
    registry.complete(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        idempotency_key="complete",
        occurred_at_ms=130,
    )
    with pytest.raises(ValueError, match="terminal task"):
        registry.attach_artifact(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            artifact_id="artifact-other",
            idempotency_key="attach-terminal",
            occurred_at_ms=140,
        )



def test_phase9_retry_and_timeout_policy_are_durable_and_deterministic() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = DurableTaskRegistry(event_store=events, idempotency_store=claims)
    retry_policy = RetryPolicy(
        max_attempts=4,
        initial_backoff_ms=100,
        max_backoff_ms=250,
        retryable_statuses=("temporary_failure", "rate_limited"),
    )
    timeout_policy = TimeoutPolicy(
        attempt_timeout_ms=5_000,
        task_deadline_ms=50_000,
    )
    created = registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-policy",
        idempotency_key="create-policy",
        retry_policy=retry_policy,
        timeout_policy=timeout_policy,
        occurred_at_ms=100,
    )
    assert created.retry_policy == retry_policy
    assert created.timeout_policy == timeout_policy
    assert retry_policy.allows_retry(attempt=1, status="temporary_failure") is True
    assert retry_policy.allows_retry(attempt=4, status="temporary_failure") is False
    assert retry_policy.allows_retry(
        attempt=1,
        status="temporary_failure",
        ambiguous=True,
    ) is False
    assert retry_policy.backoff_ms(attempt=1) == 100
    assert retry_policy.backoff_ms(attempt=2) == 200
    assert retry_policy.backoff_ms(attempt=3) == 250
    assert timeout_policy.attempt_deadline_ms(started_at_ms=1_000) == 6_000
    assert timeout_policy.is_task_timed_out(now_ms=49_999) is False
    assert timeout_policy.is_task_timed_out(now_ms=50_000) is True

    rebuilt = DurableTaskRegistry(
        event_store=events,
        idempotency_store=claims,
    ).get(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-policy",
    )
    assert rebuilt.retry_policy == retry_policy
    assert rebuilt.timeout_policy == timeout_policy


def test_phase9_retry_policy_never_blindly_retries_ambiguous_effects_by_default() -> None:
    policy = RetryPolicy(max_attempts=3)
    assert policy.allows_retry(
        attempt=1,
        status="temporary_failure",
        ambiguous=True,
    ) is False
    explicit = RetryPolicy(max_attempts=3, retry_ambiguous=True)
    assert explicit.allows_retry(
        attempt=1,
        status="temporary_failure",
        ambiguous=True,
    ) is True


def test_phase9_retry_timeout_policy_validation_fails_closed() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="max_backoff_ms"):
        RetryPolicy(max_attempts=2, initial_backoff_ms=200, max_backoff_ms=100)
    with pytest.raises(ValueError, match="attempt_timeout_ms"):
        TimeoutPolicy(attempt_timeout_ms=0)
    with pytest.raises(ValueError, match="task_deadline_ms"):
        TimeoutPolicy(task_deadline_ms=-1)
    with pytest.raises(ValueError, match="max_attempts must be an integer"):
        RetryPolicy(max_attempts=True)
    with pytest.raises(ValueError, match="retry_ambiguous must be boolean"):
        RetryPolicy.from_dict({"max_attempts": 2, "retry_ambiguous": "false"})
    with pytest.raises(ValueError, match="attempt_timeout_ms must be an integer"):
        TimeoutPolicy(attempt_timeout_ms=True)


def test_phase9_legacy_task_without_policy_payload_projects_safe_defaults() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="task:create-legacy-policy",
        tenant_id="tenant-p9",
        business_id="business-p9",
        fact_type="task.created",
        entity_id="task-legacy-policy",
        event_time_ms=100,
        observed_at_ms=100,
        source="durable_task_registry",
        payload={"title": "legacy"},
    ).as_event())
    task = DurableTaskProjector(events).get(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-legacy-policy",
    )
    assert task.retry_policy == RetryPolicy()
    assert task.timeout_policy == TimeoutPolicy()
    assert task.retry_policy.max_attempts == 1



def test_phase9_task_priority_and_conflict_keys_are_durable() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = DurableTaskRegistry(event_store=events, idempotency_store=claims)
    created = registry.create(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-conflict",
        idempotency_key="create-conflict",
        priority=90,
        conflict_keys=("customer:42", "ledger"),
        occurred_at_ms=100,
    )
    assert created.priority == 90
    assert created.conflict_keys == ("customer:42", "ledger")

    rebuilt = DurableTaskRegistry(
        event_store=events,
        idempotency_store=claims,
    ).get(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-conflict",
    )
    assert rebuilt.priority == 90
    assert rebuilt.conflict_keys == ("customer:42", "ledger")


def test_phase9_task_priority_and_conflict_metadata_fail_closed() -> None:
    with pytest.raises(ValueError, match="priority"):
        DurableTask(
            task_id="task",
            tenant_id="tenant",
            business_id="business",
            priority=101,
        )
    with pytest.raises(ValueError, match="conflict_key"):
        DurableTask(
            task_id="task",
            tenant_id="tenant",
            business_id="business",
            conflict_keys=("   ",),
        )
