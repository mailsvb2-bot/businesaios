from __future__ import annotations

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_closed_loop_persists_capability_and_replanning_context() -> None:
    orchestrator = ClosedLoopOrchestrator()
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_id': 'a-1', 'action_type': 'notify_owner', 'tenant_id': 'tenant-1'},
            execution_receipt={'tenant_id': 'tenant-1'},
            feedback={'verified': True, 'verification_status': 'verified'},
            capability_context={'runtime': {'health_score': 0.2, 'degraded': True}, 'reason': 'degraded_mode_notify_owner'},
            replanning_context={'mode': 'operator_handoff', 'reason': 'connector_unhealthy'},
        )
    )
    assert result.persisted_memory_evidence['capability']['reason'] == 'degraded_mode_notify_owner'
    assert result.persisted_memory_evidence['capability_replanning']['mode'] == 'operator_handoff'
    assert result.next_tier_context['capability_replanning']['reason'] == 'connector_unhealthy'
