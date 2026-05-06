from __future__ import annotations

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator
from execution.evidence_persistence import EvidencePersistenceService
from execution.idempotency_guard import FileIdempotencyGuard


def test_file_idempotency_guard_persists_resolution_metadata(tmp_path):
    guard = FileIdempotencyGuard(root_dir=tmp_path / 'idem')
    first = guard.claim_details(key='goal-1')
    second = guard.claim_details(key='goal-1')
    assert first.accepted is True
    assert second.accepted is False
    meta = guard.metadata(key='goal-1')
    assert meta is not None
    assert meta['resolution'] in {'accepted', 'rejected_in_progress'}


def test_evidence_persistence_builds_receipt():
    payload = EvidencePersistenceService().build_feedback_artifacts(
        verification_result={
            'verified': True,
            'verification': {'status': 'accepted', 'external_refs': ['msg:1']},
            'evidence_bundle': {'action_type': 'send_email', 'action_id': 'a1', 'external_refs': ['msg:1']},
        }
    )
    assert payload['persistence_receipt']['persistence_key']


def test_closed_loop_orchestrator_emits_reliability_trace():
    result = ClosedLoopOrchestrator().run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'publish_page', 'action_id': 'act-1', 'decision_id': 'dec-1', 'correlation_id': 'corr-1'},
            world_state={'meta': {}},
            execution_receipt={'status': 'executed', 'decision_id': 'dec-1', 'correlation_id': 'corr-1'},
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
        )
    )
    assert result.reliability_trace['trace_key']
    assert result.persisted_memory_evidence['reliability_trace']['trace_key'] == result.reliability_trace['trace_key']
    assert result.next_tier_context['closed_loop_trace_key'] == result.reliability_trace['trace_key']



def test_closed_loop_orchestrator_exposes_effect_delivery_metadata():
    result = ClosedLoopOrchestrator().run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'publish_page', 'action_id': 'act-1', 'decision_id': 'dec-1', 'correlation_id': 'corr-1'},
            world_state={'meta': {}},
            execution_receipt={'status': 'executed', 'decision_id': 'dec-1', 'correlation_id': 'corr-1'},
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
        )
    )
    assert result.persisted_memory_evidence['effect_delivery']['effect_key']
    assert result.persisted_memory_evidence['effect_delivery']['delivery_guarantee'] == 'exactly_once_effect_scope'
    assert result.next_tier_context['effect_delivery']['delivery_guarantee'] == 'exactly_once_effect_scope'
