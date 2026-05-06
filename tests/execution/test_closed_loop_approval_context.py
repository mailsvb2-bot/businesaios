from __future__ import annotations

import pytest

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_closed_loop_rejects_operator_required_context_without_explicit_execution_id() -> None:
    orchestrator = ClosedLoopOrchestrator()
    with pytest.raises(ValueError, match='approval_context_requires_explicit_execution_id'):
        orchestrator.run_cycle(
            cycle_input=ClosedLoopCycleInput(
                action={'action_type': 'email', 'decision_id': 'dec-1', 'tenant_id': 'acme'},
                execution_receipt={'tenant_id': 'acme'},
                approval_context={
                    'tenant_id': 'acme',
                    'decision_id': 'dec-1',
                    'approval_required': True,
                    'operator_required': True,
                    'approval_id': 'ap-1',
                    'subject_fingerprint': 'fp-1',
                },
            )
        )


def test_closed_loop_normalizes_used_operator_override_alias() -> None:
    orchestrator = ClosedLoopOrchestrator()
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'email', 'decision_id': 'dec-1', 'tenant_id': 'acme'},
            execution_receipt={'tenant_id': 'acme'},
            approval_context={
                'tenant_id': 'acme',
                'execution_id': 'exec-1',
                'decision_id': 'dec-1',
                'approval_required': True,
                'operator_required': True,
                'approval_id': 'ap-1',
                'subject_fingerprint': 'fp-1',
                'used_operator_override': True,
                'reason': 'operator_override_approved_once',
            },
        )
    )
    approval = result.persisted_memory_evidence['approval']
    assert approval['manual_override_used'] is True
    assert result.next_tier_context['operator_handoff']['manual_override_used'] is True


def test_closed_loop_derives_approval_context_from_execution_receipt() -> None:
    orchestrator = ClosedLoopOrchestrator()
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'email', 'decision_id': 'dec-9', 'tenant_id': 'acme'},
            execution_receipt={
                'tenant_id': 'acme',
                'approval': {
                    'tenant_id': 'acme',
                    'execution_id': 'exec-9',
                    'decision_id': 'dec-9',
                    'approval_required': True,
                    'operator_required': True,
                    'approval_id': 'ap-9',
                    'subject_fingerprint': 'fp-9',
                    'reason': 'approval_submitted_awaiting_operator',
                },
            },
        )
    )
    assert result.persisted_memory_evidence['approval']['approval_id'] == 'ap-9'
    assert result.next_tier_context['approval']['subject_fingerprint'] == 'fp-9'
