from __future__ import annotations

import pytest

from reliability.execution_checkpoint_store import (
    ExecutionCheckpoint,
    InMemoryExecutionCheckpointStore,
    JsonlExecutionCheckpointStore,
)


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
