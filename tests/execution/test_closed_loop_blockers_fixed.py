from __future__ import annotations

import pytest

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_closed_loop_reuses_receipt_budget_without_reconsuming() -> None:
    orchestrator = ClosedLoopOrchestrator()
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'email', 'tenant_id': 'acme', 'queue_name': 'campaigns', 'action_count': 2},
            execution_receipt={'tenant_id': 'acme', 'queue_name': 'campaigns', 'tenant_budget': {'allowed': True, 'reason': 'tenant_execution_budget_consumed', 'tenant_id': 'acme', 'violations': [], 'consumed': True}},
            world_state={'meta': {}},
        )
    )
    assert result.persisted_memory_evidence['tenant_budget']['consumed'] is True
    assert result.persisted_memory_evidence['tenant_budget']['reason'] == 'tenant_execution_budget_consumed'


def test_closed_loop_rejects_queue_mismatch() -> None:
    orchestrator = ClosedLoopOrchestrator()
    with pytest.raises(ValueError):
        orchestrator.run_cycle(
            cycle_input=ClosedLoopCycleInput(
                action={'action_type': 'email', 'tenant_id': 'acme', 'queue_name': 'campaigns'},
                execution_receipt={'tenant_id': 'acme', 'queue_name': 'other'},
                world_state={'meta': {}},
            )
        )
