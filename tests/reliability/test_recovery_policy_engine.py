from __future__ import annotations

from reliability.execution_checkpoint_store import ExecutionCheckpoint, InMemoryExecutionCheckpointStore
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage
from reliability.recovery_policy_engine import RecoveryPolicyEngine


def test_recovery_policy_engine_prefers_delivery_resume_for_claimable_outbox() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-1', namespace='runtime', operation='execute', key='run-1', scope_hash='scope-1')
    idempotency.reserve(key=key, owner_id='owner-a')
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=0,
            stage='request',
            checkpoint_id='cp-0',
        )
    )
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=1,
            stage='world_state',
            checkpoint_id='cp-1',
        )
    )
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=2,
            stage='decision',
            checkpoint_id='cp-2',
            idempotency_key='run-1',
        )
    )
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=3,
            stage='executable_action',
            checkpoint_id='cp-3',
            idempotency_key='run-1',
        )
    )
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=4,
            stage='execution',
            checkpoint_id='cp-4',
            idempotency_key='run-1',
            outbox_message_id='msg-1',
        )
    )
    outbox.enqueue(
        OutboxMessage(
            tenant_id='tenant-1',
            message_id='msg-1',
            topic='effects',
            dedupe_key='d-1',
            payload={'ok': True},
            run_id='run-1',
        )
    )

    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).resolve(tenant_id='tenant-1', run_id='run-1', idempotency_key=key, outbox_message_id='msg-1')

    assert decision.action == 'resume_delivery'
    assert decision.resume_stage == 'execution'
    assert decision.operator_required is False


def test_recovery_policy_engine_quarantines_cross_store_anomaly() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-9', scope_hash='scope-9')
    idempotency.reserve(key=key, owner_id='worker-1')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-9', sequence_no=0, stage='request', checkpoint_id='cp-0'))
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-9', sequence_no=1, stage='completed', checkpoint_id='cp-1', idempotency_key='run-9'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-9', topic='effects', dedupe_key='d-9', payload={'ok': True}, run_id='run-9'))

    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).resolve(tenant_id='tenant-a', run_id='run-9', idempotency_key=key, outbox_message_id='msg-9')

    assert decision.action == 'quarantine'
    assert 'completed_run_without_completed_idempotency' in decision.anomalies
