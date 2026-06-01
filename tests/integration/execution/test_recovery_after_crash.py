from __future__ import annotations

from datetime import timedelta

from reliability.execution_checkpoint_store import ExecutionCheckpoint, InMemoryExecutionCheckpointStore
from reliability.execution_checkpoint_store import utc_now as checkpoint_now
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState
from reliability.recovery_orchestrator import RecoveryOrchestrator


def test_recovery_after_crash_resumes_expired_outbox_delivery() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    now = checkpoint_now()

    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-77', scope_hash='scope-77')
    idempotency.reserve(key=key, owner_id='worker-a', now=now)
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-77', sequence_no=1, stage='execution', checkpoint_id='cp-1', outbox_message_id='msg-77'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-77', topic='effects', dedupe_key='d-77', payload={'ok': True}, created_at=now, updated_at=now, available_at=now))
    claimed = outbox.claim(tenant_id='tenant-a', message_id='msg-77', owner_id='worker-a', claim_ttl_seconds=1, now=now)
    assert claimed is not None
    assert claimed.state is OutboxState.DELIVERING

    orchestrator = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox)
    plan = orchestrator.plan(
        tenant_id='tenant-a',
        run_id='run-77',
        idempotency_key=key,
        outbox_message_id='msg-77',
    )

    assert plan.recovery_action in {'wait', 'resume_delivery'}

    reclaimed = outbox.claim(
        tenant_id='tenant-a',
        message_id='msg-77',
        owner_id='worker-b',
        claim_ttl_seconds=30,
        now=now + timedelta(seconds=2),
    )
    assert reclaimed is not None
    assert reclaimed.claim_owner_id == 'worker-b'

    resumed_plan = orchestrator.plan(
        tenant_id='tenant-a',
        run_id='run-77',
        idempotency_key=key,
        outbox_message_id='msg-77',
    )
    assert resumed_plan.delivery_hint in {'expired_delivery_claim_can_be_stolen', None}


def test_recovery_after_crash_quarantines_late_stage_without_outbox_record() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-88', scope_hash='scope-88')
    idempotency.reserve(key=key, owner_id='worker-a')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-88', sequence_no=1, stage='verification', checkpoint_id='cp-1'))

    plan = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).plan(
        tenant_id='tenant-a', run_id='run-88', idempotency_key=key
    )

    assert plan.recovery_action == 'quarantine'
    assert 'late_stage_without_outbox_record' in plan.anomalies
