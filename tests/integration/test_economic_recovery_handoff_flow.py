from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_economic_recovery_handoff_flow_persists_bundle_and_handoff(tmp_path: Path) -> None:
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=tmp_path / 'runtime_data')
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={
                'action_type': 'publish_page',
                'action_id': 'econ-recovery-1',
                'decision_id': 'dec-econ-recovery-1',
                'run_id': 'run-econ-recovery-1',
                'channel': 'web',
            },
            world_state={'meta': {}},
            execution_receipt={
                'status': 'executed',
                'decision_id': 'dec-econ-recovery-1',
                'recovery': {'action': 'resume', 'reason': 'worker_restart', 'operator_required': False},
            },
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
            requested_tier='supervised',
            current_tier='supervised',
        )
    )
    payload = result.persisted_memory_evidence
    assert payload['economic_audit_bundle']['bundle_id'] == payload['economic_event_id']
    assert payload['economic_metrics_snapshot']['snapshot_id'] == payload['economic_event_id']
    assert payload['economic_recovery_handoff']['recovery_action'] == 'resume'
    assert result.world_state['meta']['economic_recovery_handoff']['economic_bundle_id'] == payload['economic_event_id']
