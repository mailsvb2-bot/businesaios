from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from execution.evidence_persistence import EvidencePersistenceService
from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore
from storage.evidence_store import InMemoryEvidenceStore


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


def test_evidence_persistence_writes_one_canonical_record_and_replays_idempotently() -> None:
    evidence_store = InMemoryEvidenceStore()
    service = EvidencePersistenceService(evidence_store=evidence_store)
    kwargs = dict(
        tenant_id='tenant-1', business_id='biz-1', run_id='run-canonical', goal='Grow revenue', step_index=1,
        action={
            'action_type': 'send_email', 'action_id': 'act-canonical', 'decision_id': 'dec-canonical',
            'derived_fact_ref': 'semantic-state-canonical',
            'evidence_refs': ['evidence-world-1', 'evidence-world-2'],
        },
        execution_result={'executed': True, 'source_of_truth': 'provider_receipt'},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:canonical']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-canonical', 'external_refs': ['msg:canonical']},
        },
        world_state_before={}, world_state_after={},
        final_feedback={
            'verification_status': 'accepted',
            'business_outcome': {
                'outcome_id': 'outcome:act-canonical',
                'source_of_truth': 'provider_receipt',
                'derived_fact_ref': 'semantic-state-canonical',
            },
        },
    )
    first = service.persist(**kwargs)
    first_rows = evidence_store.list_for_tenant(tenant_id='tenant-1')
    assert len(first_rows) == 1
    record = first_rows[0]
    assert record.business_id == 'biz-1'
    assert record.refs == ('evidence-world-1', 'evidence-world-2', 'msg:canonical')
    assert record.lineage['derived_fact'] == 'semantic-state-canonical'
    assert record.lineage['decision'] == 'dec-canonical'
    assert record.lineage['action'] == 'act-canonical'
    assert record.lineage['outcome'] == 'outcome:act-canonical'
    assert record.lineage['source'] == 'msg:canonical'
    assert record.lineage_complete is True
    second = service.persist(**kwargs)
    second_rows = evidence_store.list_for_tenant(tenant_id='tenant-1')
    assert len(second_rows) == 1
    assert second_rows[0] == record
    assert first.persistence_receipt['persistence_key'] == second.persistence_receipt['persistence_key']


def test_evidence_persistence_rejects_conflicting_replay_for_same_persistence_key() -> None:
    evidence_store = InMemoryEvidenceStore()
    service = EvidencePersistenceService(evidence_store=evidence_store)
    base = dict(
        tenant_id='tenant-1', business_id='biz-1', run_id='run-conflict', goal='Grow revenue', step_index=1,
        action={'action_type': 'send_email', 'action_id': 'act-conflict', 'decision_id': 'dec-conflict'},
        execution_result={'executed': True}, world_state_before={}, world_state_after={},
    )
    service.persist(
        **base,
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:first']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-conflict', 'external_refs': ['msg:first']},
        },
    )
    import pytest
    with pytest.raises(ValueError, match='canonical evidence replay conflicts'):
        service.persist(
            **base,
            verification_result={
                'verified': True,
                'verification': {'status': 'accepted', 'external_refs': ['msg:forged']},
                'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-conflict', 'external_refs': ['msg:forged']},
            },
        )



class _RacingEvidenceStore(InMemoryEvidenceStore):
    def __init__(self) -> None:
        super().__init__()
        self._first_read_barrier = Barrier(2)

    def get(self, *, tenant_id: str, evidence_id: str):
        existing = super().get(tenant_id=tenant_id, evidence_id=evidence_id)
        if existing is None:
            self._first_read_barrier.wait(timeout=5)
        return existing


def test_concurrent_identical_evidence_replay_reconciles_to_one_record() -> None:
    evidence_store = _RacingEvidenceStore()
    service = EvidencePersistenceService(evidence_store=evidence_store)
    kwargs = dict(
        tenant_id='tenant-1', business_id='biz-1', run_id='run-race', goal='Grow revenue', step_index=1,
        action={'action_type': 'send_email', 'action_id': 'act-race', 'decision_id': 'dec-race'},
        execution_result={'executed': True, 'source_of_truth': 'provider_receipt'},
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:race']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'act-race', 'external_refs': ['msg:race']},
        },
        world_state_before={}, world_state_after={},
        final_feedback={
            'verification_status': 'accepted',
            'business_outcome': {'outcome_id': 'outcome:act-race', 'source_of_truth': 'provider_receipt'},
        },
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.persist, **kwargs) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    rows = evidence_store.list_for_tenant(tenant_id='tenant-1')
    assert len(rows) == 1
    assert len({result.persistence_receipt['persistence_key'] for result in results}) == 1
    assert rows[0].lineage['outcome'] == 'outcome:act-race'
