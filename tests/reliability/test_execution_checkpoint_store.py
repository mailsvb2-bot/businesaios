from __future__ import annotations

from types import SimpleNamespace

import pytest

from reliability.execution_checkpoint_store import (
    ExecutionCheckpoint,
    InMemoryExecutionCheckpointStore,
    JsonlExecutionCheckpointStore,
)
from runtime.execution.reliability_runtime import RuntimeReliability


def test_execution_checkpoint_store_enforces_monotonic_sequence_and_stage_order(tmp_path) -> None:
    store = InMemoryExecutionCheckpointStore()
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-1', sequence_no=1, stage='request', checkpoint_id='cp-1'))
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-1', sequence_no=2, stage='world_state', checkpoint_id='cp-2'))
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-1', sequence_no=3, stage='decision', checkpoint_id='cp-3'))

    latest = store.latest(tenant_id='tenant-a', run_id='run-1')

    assert latest is not None
    assert latest.stage == 'decision'

    path = tmp_path / 'checkpoints.jsonl'
    jsonl = JsonlExecutionCheckpointStore(path)
    for item in store.list_run(tenant_id='tenant-a', run_id='run-1'):
        jsonl.append(item)
    assert jsonl.latest(tenant_id='tenant-a', run_id='run-1').checkpoint_id == 'cp-3'


def test_execution_checkpoint_store_persists_failed_terminal_stage_without_backward_progression() -> None:
    store = InMemoryExecutionCheckpointStore()
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-2', sequence_no=1, stage='request', checkpoint_id='cp-1'))
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-2', sequence_no=2, stage='failed', checkpoint_id='cp-2'))

    latest = store.latest(tenant_id='tenant-a', run_id='run-2')

    assert latest is not None
    assert latest.stage == 'failed'


def test_execution_checkpoint_store_rejects_backward_stage_and_non_monotonic_sequence() -> None:
    store = InMemoryExecutionCheckpointStore()
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-3', sequence_no=1, stage='request', checkpoint_id='cp-1'))
    store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-3', sequence_no=2, stage='world_state', checkpoint_id='cp-2'))

    with pytest.raises(ValueError, match='strictly increase'):
        store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-3', sequence_no=2, stage='decision', checkpoint_id='cp-3'))

    with pytest.raises(ValueError, match='must not move backwards'):
        store.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-3', sequence_no=3, stage='request', checkpoint_id='cp-4'))



def test_task_scoped_checkpoints_survive_store_rebuild_and_are_business_isolated(tmp_path) -> None:
    path = tmp_path / "task-checkpoints.jsonl"
    first = JsonlExecutionCheckpointStore(path)
    first.append(
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            business_id="business-a",
            task_id="task-a",
            step_id="step-1",
            run_id="run-1",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-1",
        )
    )
    first.append(
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            business_id="business-a",
            task_id="task-a",
            step_id="step-1",
            run_id="run-1",
            sequence_no=2,
            stage="decision",
            checkpoint_id="cp-2",
        )
    )

    rebuilt = JsonlExecutionCheckpointStore(path)
    latest = rebuilt.latest_for_task(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
    )
    assert latest is not None
    assert latest.checkpoint_id == "cp-2"
    assert latest.step_id == "step-1"
    assert rebuilt.list_task(
        tenant_id="tenant-a",
        business_id="business-b",
        task_id="task-a",
    ) == ()


def test_task_scoped_checkpoint_requires_complete_scope() -> None:
    with pytest.raises(ValueError, match="requires business_id"):
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            task_id="task-a",
            run_id="run-1",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-1",
        ).validate()
    with pytest.raises(ValueError, match="requires task_id"):
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            business_id="business-a",
            step_id="step-1",
            run_id="run-1",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-1",
        ).validate()


def test_checkpoint_id_must_be_unique_across_entire_run() -> None:
    store = InMemoryExecutionCheckpointStore()
    store.append(
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            run_id="run-1",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-shared",
        )
    )
    store.append(
        ExecutionCheckpoint(
            tenant_id="tenant-a",
            run_id="run-1",
            sequence_no=2,
            stage="world_state",
            checkpoint_id="cp-2",
        )
    )
    with pytest.raises(ValueError, match="checkpoint_id must be unique"):
        store.append(
            ExecutionCheckpoint(
                tenant_id="tenant-a",
                run_id="run-1",
                sequence_no=3,
                stage="decision",
                checkpoint_id="cp-shared",
            )
        )



def _runtime_reliability_for_checkpoint_test() -> RuntimeReliability:
    return RuntimeReliability(
        checkpoint_store=InMemoryExecutionCheckpointStore(),
        idempotency_store=None,
        recovery_orchestrator=None,
        distributed_lock=None,
        scheduler_leader_election=None,
        recovery_leader_election=None,
    )


def test_runtime_reliability_projects_only_explicit_task_scope_into_checkpoint() -> None:
    runtime = _runtime_reliability_for_checkpoint_test()
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-task",
            correlation_id="trace-task",
            action="send_message@v1",
            payload={
                "tenant_id": "tenant-a",
                "business_id": "business-a",
                "task_id": "task-a",
                "step_id": "step-a",
                "idempotency_key": "idem-a",
            },
        )
    )
    checkpoint = runtime.append_checkpoint(
        env,
        stage="request",
        checkpoint_id="task-request",
    )
    assert checkpoint.business_id == "business-a"
    assert checkpoint.task_id == "task-a"
    assert checkpoint.step_id == "step-a"
    rebuilt = runtime.checkpoint_store.latest_for_task(
        tenant_id="tenant-a",
        business_id="business-a",
        task_id="task-a",
    )
    assert rebuilt == checkpoint


def test_runtime_reliability_fails_closed_on_incomplete_task_scope() -> None:
    runtime = _runtime_reliability_for_checkpoint_test()
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-task",
            correlation_id="trace-task",
            action="send_message@v1",
            payload={
                "tenant_id": "tenant-a",
                "task_id": "task-a",
                "idempotency_key": "idem-a",
            },
        )
    )
    with pytest.raises(ValueError, match="requires business_id"):
        runtime.append_checkpoint(
            env,
            stage="request",
            checkpoint_id="task-request",
        )



def test_runtime_reliability_does_not_invent_task_scope_for_legacy_decision() -> None:
    runtime = _runtime_reliability_for_checkpoint_test()
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-legacy",
            correlation_id="trace-legacy",
            action="noop@v1",
            payload={
                "tenant_id": "tenant-a",
                "business_id": "business-a",
                "idempotency_key": "idem-legacy",
            },
        )
    )
    checkpoint = runtime.append_checkpoint(
        env,
        stage="request",
        checkpoint_id="legacy-request",
    )
    assert checkpoint.business_id == "business-a"
    assert checkpoint.task_id is None
    assert checkpoint.step_id is None



def test_phase9_task_run_and_step_projection_reuses_checkpoint_owner(tmp_path) -> None:
    path = tmp_path / "run-step-checkpoints.jsonl"
    store = JsonlExecutionCheckpointStore(path)
    rows = (
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            step_id="step-a",
            run_id="executor-run-1",
            task_run_id="task-run-a",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-1",
        ),
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            step_id="step-a",
            run_id="executor-run-1",
            task_run_id="task-run-a",
            sequence_no=2,
            stage="execution",
            checkpoint_id="cp-2",
        ),
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_id="task-p9",
            step_id="step-b",
            run_id="executor-run-2",
            task_run_id="task-run-a",
            sequence_no=3,
            stage="completed",
            checkpoint_id="cp-3",
        ),
    )
    for row in rows:
        store.append(row)

    rebuilt = JsonlExecutionCheckpointStore(path)
    runs = rebuilt.list_task_runs(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
    )
    assert len(runs) == 1
    assert runs[0].run_id == "task-run-a"
    assert runs[0].checkpoint_count == 3
    assert runs[0].terminal_stage == "completed"

    steps = rebuilt.list_run_steps(
        tenant_id="tenant-p9",
        business_id="business-p9",
        task_id="task-p9",
        run_id="task-run-a",
    )
    assert [item.step_id for item in steps] == ["step-a", "step-b"]
    assert steps[0].first_sequence_no == 1
    assert steps[0].last_sequence_no == 2
    assert steps[0].checkpoint_count == 2
    assert steps[0].latest_stage == "execution"
    assert steps[1].latest_stage == "completed"


def test_phase9_run_step_projection_is_business_and_task_isolated() -> None:
    store = InMemoryExecutionCheckpointStore()
    store.append(
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-a",
            task_id="task-a",
            step_id="step-a",
            run_id="executor-a",
            task_run_id="run-shared",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-a",
        )
    )
    store.append(
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-b",
            task_id="task-b",
            step_id="step-b",
            run_id="executor-b",
            task_run_id="run-shared",
            sequence_no=2,
            stage="decision",
            checkpoint_id="cp-b",
        )
    )

    runs = store.list_task_runs(
        tenant_id="tenant-p9",
        business_id="business-a",
        task_id="task-a",
    )
    assert [item.run_id for item in runs] == ["run-shared"]
    steps = store.list_run_steps(
        tenant_id="tenant-p9",
        business_id="business-a",
        task_id="task-a",
        run_id="run-shared",
    )
    assert [item.step_id for item in steps] == ["step-a"]



def test_phase9_task_run_scope_requires_task_identity() -> None:
    with pytest.raises(ValueError, match="task run checkpoint requires task_id"):
        ExecutionCheckpoint(
            tenant_id="tenant-p9",
            business_id="business-p9",
            task_run_id="task-run-a",
            run_id="executor-run-a",
            sequence_no=1,
            stage="request",
            checkpoint_id="cp-run-scope",
        ).validate()
