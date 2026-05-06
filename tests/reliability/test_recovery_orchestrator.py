from __future__ import annotations

from reliability.execution_checkpoint_store import ExecutionCheckpoint, InMemoryExecutionCheckpointStore
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage
from reliability.recovery_orchestrator import RecoveryOrchestrator


def test_recovery_orchestrator_prefers_delivery_resume_for_claimable_outbox() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()

    key = IdempotencyKey(tenant_id='tenant-1', namespace='runtime', operation='execute', key='run-1', scope_hash='scope-1')
    idempotency.reserve(key=key, owner_id='owner-a')
    checkpoints.append(
        ExecutionCheckpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            sequence_no=1,
            stage='execution',
            checkpoint_id='cp-1',
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
        )
    )

    orchestrator = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox)
    plan = orchestrator.plan(tenant_id='tenant-1', run_id='run-1', idempotency_key=key, outbox_message_id='msg-1')

    assert plan.recovery_action == 'resume_delivery'
    assert plan.delivery_hint == 'pending_delivery_can_be_claimed'
    assert plan.reconciliation.is_clean is True


def test_recovery_orchestrator_quarantines_anomalous_completed_run() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()

    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-9', scope_hash='scope-9')
    idempotency.reserve(key=key, owner_id='worker-1')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-9', sequence_no=1, stage='completed', checkpoint_id='cp-1'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-9', topic='effects', dedupe_key='d-9', payload={'ok': True}))

    orchestrator = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox)
    plan = orchestrator.plan(tenant_id='tenant-a', run_id='run-9', idempotency_key=key, outbox_message_id='msg-9')

    assert plan.recovery_action == 'quarantine'
    assert 'completed_checkpoint_but_idempotency_not_completed' in plan.anomalies
    assert plan.reason == 'reconciliation_anomaly'


def test_recovery_orchestrator_restarts_when_no_checkpoint_exists() -> None:
    orchestrator = RecoveryOrchestrator(
        checkpoint_store=InMemoryExecutionCheckpointStore(),
        idempotency_store=InMemoryIdempotencyStore(),
        outbox_store=InMemoryOutboxStore(),
    )

    plan = orchestrator.plan(tenant_id='tenant-a', run_id='missing-run')

    assert plan.recovery_action == 'restart'
    assert plan.reason == 'no_checkpoint'


def test_recovery_orchestrator_noops_for_clean_completed_terminal_run() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-done', scope_hash='scope-done')
    idempotency.reserve(key=key, owner_id='worker')
    idempotency.mark_completed(key=key, owner_id='worker', result_ref='result://run-done', result_digest='digest-run-done')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-done', sequence_no=1, stage='completed', checkpoint_id='cp-1'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-done', topic='effects', dedupe_key='d-done', payload={'ok': True}))
    claimed = outbox.claim(tenant_id='tenant-a', message_id='msg-done', owner_id='worker')
    assert claimed is not None
    outbox.mark_delivered(tenant_id='tenant-a', message_id='msg-done', owner_id='worker')

    plan = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).plan(
        tenant_id='tenant-a', run_id='run-done', idempotency_key=key, outbox_message_id='msg-done'
    )

    assert plan.recovery_action == 'noop'
    assert plan.reason == 'terminal_completed'
