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
