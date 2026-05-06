from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_economic_bundle_catalog_chain_flow_persists_manifest_entry_and_reconciliation(tmp_path: Path) -> None:
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=tmp_path / 'runtime_data')
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={
                'action_type': 'publish_page',
                'action_id': 'econ-chain-1',
                'decision_id': 'dec-econ-chain-1',
                'run_id': 'run-econ-chain-1',
                'channel': 'web',
            },
            world_state={'meta': {}},
            execution_receipt={
                'status': 'executed',
                'decision_id': 'dec-econ-chain-1',
                'recovery': {'action': 'resume', 'reason': 'worker_restart', 'operator_required': False},
            },
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
            requested_tier='supervised',
            current_tier='supervised',
        )
    )
    payload = result.persisted_memory_evidence
    assert payload['economic_audit_bundle_entry']['bundle_kind'] == 'economic'
    assert payload['economic_export_manifest']['bundle']['exists'] is True
    assert payload['economic_bundle_reconciliation']['consistent'] is True
    assert Path(payload['economic_audit_bundle_entry']['path']).exists()
    assert result.world_state['meta']['economic_bundle_reconciliation']['consistent'] is True
