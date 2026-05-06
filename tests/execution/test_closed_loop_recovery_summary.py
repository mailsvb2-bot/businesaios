from __future__ import annotations

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_closed_loop_orchestrator_carries_recovery_summary_without_deciding() -> None:
    result = ClosedLoopOrchestrator().run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'publish_page', 'action_id': 'act-1', 'decision_id': 'dec-1', 'correlation_id': 'corr-1'},
            world_state={'meta': {}},
            execution_receipt={
                'status': 'executed',
                'decision_id': 'dec-1',
                'correlation_id': 'corr-1',
                'recovery_plan': {
                    'recovery_action': 'resume_delivery',
                    'reason': 'claimable_outbox_after_execution',
                    'resume_stage': 'execution',
                    'operator_required': False,
                    'delivery_hint': 'pending_delivery_can_be_claimed',
                    'anomalies': [],
                },
                'reconciliation': {
                    'latest_stage': 'execution',
                    'outbox_state': 'pending',
                    'idempotency_state': 'in_progress',
                    'anomalies': [],
                },
            },
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
        )
    )

    recovery = result.persisted_memory_evidence['recovery']
    assert recovery['action'] == 'resume_delivery'
    assert recovery['resume_stage'] == 'execution'
    assert result.next_tier_context['recovery']['outbox_state'] == 'pending'
