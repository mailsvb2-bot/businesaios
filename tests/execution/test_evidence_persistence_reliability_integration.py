from __future__ import annotations

from execution.evidence_persistence import EvidencePersistenceService
from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore


def _service() -> EvidencePersistenceService:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    reconciliation = ExecutionReconciliation(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    )
    return EvidencePersistenceService(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
        reconciliation_service=reconciliation,
    )


def test_evidence_persistence_persists_reliability_receipt() -> None:
    service = _service()
    artifacts = service.persist(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-1',
        goal='Grow revenue',
        step_index=2,
        action={'action_type': 'send_email', 'action_id': 'act-1'},
        execution_result={'executed': True},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:1']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-1', 'external_refs': ['msg:1']},
        },
        world_state_before={},
        world_state_after={},
    )
    receipt = artifacts.persistence_receipt
    assert receipt is not None
    assert receipt['idempotency_resolution'] in {'accepted', 'disabled'}
    assert receipt['outbox_message_id']
    assert 'outbox_state' in receipt['reconciliation']
    assert receipt['reconciliation']['latest_stage'] in {'completed', 'evidence'}


def test_evidence_persistence_is_idempotent_for_same_payload() -> None:
    service = _service()
    common_kwargs = dict(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-1',
        goal='Grow revenue',
        step_index=2,
        action={'action_type': 'send_email', 'action_id': 'act-1'},
        execution_result={'executed': True},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:1']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-1', 'external_refs': ['msg:1']},
        },
        world_state_before={},
        world_state_after={},
    )
    first = service.persist(**common_kwargs)
    second = service.persist(**common_kwargs)
    assert first.persistence_receipt['persistence_key'] == second.persistence_receipt['persistence_key']
    assert second.persistence_receipt['idempotency_resolution'] == 'replay_completed'
    assert second.persistence_receipt['replayed'] is True


def test_build_feedback_artifacts_includes_reliability_metadata() -> None:
    service = _service()
    payload = service.build_feedback_artifacts(
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:1']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'a1', 'external_refs': ['msg:1']},
        }
    )
    receipt = payload['persistence_receipt']
    assert receipt['persistence_key']
    assert 'idempotency_resolution' in receipt
    assert 'outbox_message_id' in receipt


class _ReplayGuard:
    def __init__(self, blocked_key: str) -> None:
        self._blocked_key = blocked_key

    def is_replay(self, *, tenant_id: str, run_id: str, persistence_key: str) -> bool:
        return persistence_key == self._blocked_key


def test_evidence_persistence_replay_guard_short_circuits_side_effects() -> None:
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    reconciliation = ExecutionReconciliation(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
    )
    probe = EvidencePersistenceService(
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
        outbox_store=outbox,
        reconciliation_service=reconciliation,
    )
    baseline = probe.persist(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-guard',
        goal='Grow revenue',
        step_index=3,
        action={'action_type': 'send_email', 'action_id': 'act-guard'},
        execution_result={'executed': True},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:guard']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-guard', 'external_refs': ['msg:guard']},
        },
        world_state_before={},
        world_state_after={},
    )
    blocked_key = baseline.persistence_receipt['persistence_key']
    guarded = EvidencePersistenceService(
        checkpoint_store=checkpoints,
        idempotency_store=None,
        outbox_store=outbox,
        replay_guard=_ReplayGuard(blocked_key=blocked_key),
        reconciliation_service=reconciliation,
    )
    replayed = guarded.persist(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-guard',
        goal='Grow revenue',
        step_index=3,
        action={'action_type': 'send_email', 'action_id': 'act-guard'},
        execution_result={'executed': True},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:guard']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-guard', 'external_refs': ['msg:guard']},
        },
        world_state_before={},
        world_state_after={},
    )
    assert replayed.persistence_receipt['replayed'] is True
    assert replayed.persistence_receipt['idempotency_resolution'] == 'replay_detected'
    assert len(checkpoints.list_run(tenant_id='tenant-1', run_id='run-guard')) == 2


def test_evidence_persistence_receipt_exposes_exactly_once_effect_scope() -> None:
    service = _service()
    artifacts = service.persist(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-effect',
        goal='Grow revenue',
        step_index=1,
        action={'action_type': 'send_email', 'action_id': 'act-effect'},
        execution_result={'executed': True},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:effect']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-effect', 'external_refs': ['msg:effect']},
        },
        world_state_before={},
        world_state_after={},
    )
    receipt = artifacts.persistence_receipt
    assert receipt['delivery_guarantee'] == 'exactly_once_effect_scope'
    assert receipt['effect_key'] == receipt['persistence_key']
    assert receipt['outbox_topic'] == 'execution.effect.send_email'
    assert receipt['outbox_payload_digest']
