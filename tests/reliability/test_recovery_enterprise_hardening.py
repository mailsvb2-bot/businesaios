from __future__ import annotations

from datetime import timedelta

from reliability.execution_checkpoint_store import ExecutionCheckpoint, InMemoryExecutionCheckpointStore, utc_now
from reliability.idempotency_contract import IdempotencyKey
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState
from reliability.recovery_orchestrator import RecoveryOrchestrator
from reliability.recovery_policy_engine import RecoveryPolicyConfig, RecoveryPolicyEngine
from reliability.recovery_run_rebuilder import RecoveryRunRebuilder
from runtime.executor_runtime_support import build_executor_recovery_support


def test_recovery_run_rebuilder_marks_partial_history_and_canonical_refs() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-1', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-1', sequence_no=4, stage='execution', checkpoint_id='cp-4', idempotency_key='run-1', outbox_message_id='msg-1', trace_id='trace-1', decision_id='dec-1'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'ok': True}, run_id='run-1'))

    facts = RecoveryRunRebuilder(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).rebuild(
        tenant_id='tenant-a', run_id='run-1', idempotency_key=key, outbox_message_id='msg-1'
    )

    assert facts.partial_history_detected is True
    assert facts.canonical_outbox_message_id == 'msg-1'
    assert facts.canonical_idempotency_key == 'run-1'
    assert facts.derived_flags['inferred_entry_stage'] == 'execution'


def test_recovery_policy_engine_can_quarantine_partial_history_when_disabled() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-2', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-2', sequence_no=4, stage='execution', checkpoint_id='cp-4', idempotency_key='run-2', outbox_message_id='msg-2'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-2', topic='effects', dedupe_key='d-2', payload={'ok': True}, run_id='run-2'))

    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
        config=RecoveryPolicyConfig(allow_partial_history_resume=False),
    ).resolve(tenant_id='tenant-a', run_id='run-2', idempotency_key=key, outbox_message_id='msg-2')

    assert decision.action == 'quarantine'
    assert decision.reason == 'partial_history_not_allowed_by_policy'
    assert 'partial_history' in decision.risk_flags


def test_recovery_policy_engine_quarantines_reference_drift() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-3', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-3', sequence_no=1, stage='execution', checkpoint_id='cp-1', idempotency_key='run-3', outbox_message_id='msg-real'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-real', topic='effects', dedupe_key='d-3', payload={'ok': True}, run_id='run-3'))

    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    ).resolve(tenant_id='tenant-a', run_id='run-3', idempotency_key=key, outbox_message_id='msg-other')

    assert decision.action == 'quarantine'
    assert decision.reason == 'explicit_reference_drift'


def test_recovery_policy_engine_prefers_resume_delivery_over_live_lease() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    now = utc_now()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-4', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker', now=now)
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-4', sequence_no=1, stage='execution', checkpoint_id='cp-1', idempotency_key='run-4', outbox_message_id='msg-4'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-4', topic='effects', dedupe_key='d-4', payload={'ok': True}, run_id='run-4'))

    decision = RecoveryPolicyEngine(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
        config=RecoveryPolicyConfig(quarantine_on_any_anomaly=False),
    ).resolve(tenant_id='tenant-a', run_id='run-4', idempotency_key=key, outbox_message_id='msg-4')

    assert decision.action == 'resume_delivery'
    assert decision.delivery_hint == 'claimable_outbox'


def test_recovery_orchestrator_exposes_policy_snapshot_and_risk_flags() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-5', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-5', sequence_no=5, stage='verification', checkpoint_id='cp-5', idempotency_key='run-5', outbox_message_id='msg-5'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-5', topic='effects', dedupe_key='d-5', payload={'ok': True}, run_id='run-5'))

    plan = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).plan(
        tenant_id='tenant-a', run_id='run-5', idempotency_key=key, outbox_message_id='msg-5'
    )

    assert 'partial_history' in plan.risk_flags
    assert plan.policy_snapshot['resume_stage'] == 'verification'


def test_runtime_executor_recovery_support_exposes_elections() -> None:
    support = build_executor_recovery_support(runtime_infra=None, outbox=InMemoryOutboxStore())
    assert support.scheduler_leader_election is not None
    assert support.recovery_leader_election is not None


def test_recovery_rebuilder_detects_dead_outbox_without_error() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-6', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker')
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-6', sequence_no=1, stage='execution', checkpoint_id='cp-1', idempotency_key='run-6', outbox_message_id='msg-6'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-6', topic='effects', dedupe_key='d-6', payload={'ok': True}, run_id='run-6', state=OutboxState.DEAD))

    facts = RecoveryRunRebuilder(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).rebuild(
        tenant_id='tenant-a', run_id='run-6', idempotency_key=key, outbox_message_id='msg-6'
    )
    assert 'dead_outbox_missing_last_error' in facts.anomalies


def test_recovery_orchestrator_normalizes_expired_delivery_hint() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    now = utc_now()
    key = IdempotencyKey(tenant_id='tenant-a', namespace='runtime', operation='execute', key='run-7', scope_hash='scope')
    idempotency.reserve(key=key, owner_id='worker-a', now=now)
    checkpoints.append(ExecutionCheckpoint(tenant_id='tenant-a', run_id='run-7', sequence_no=1, stage='execution', checkpoint_id='cp-1', idempotency_key='run-7', outbox_message_id='msg-7'))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-7', topic='effects', dedupe_key='d-7', payload={'ok': True}, run_id='run-7', created_at=now, updated_at=now, available_at=now))
    outbox.claim(tenant_id='tenant-a', message_id='msg-7', owner_id='worker-a', claim_ttl_seconds=1, now=now)
    outbox.claim(tenant_id='tenant-a', message_id='msg-7', owner_id='worker-b', claim_ttl_seconds=30, now=now + timedelta(seconds=2))

    plan = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=outbox).plan(
        tenant_id='tenant-a', run_id='run-7', idempotency_key=key, outbox_message_id='msg-7'
    )
    assert plan.delivery_hint in {'expired_delivery_claim_can_be_stolen', 'pending_delivery_can_be_claimed', None}
