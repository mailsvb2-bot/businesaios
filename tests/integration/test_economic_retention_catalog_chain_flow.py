from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_economic_retention_manifest_and_multinode_reconciliation_flow(tmp_path: Path) -> None:
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=tmp_path / 'runtime_data')
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={
                'action_type': 'publish_page',
                'action_id': 'econ-retention-1',
                'decision_id': 'dec-econ-retention-1',
                'run_id': 'run-econ-retention-1',
                'channel': 'web',
            },
            world_state={'meta': {}},
            execution_receipt={'status': 'executed', 'decision_id': 'dec-econ-retention-1'},
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
            requested_tier='supervised',
            current_tier='supervised',
        )
    )
    payload = result.persisted_memory_evidence
    manifest = payload['economic_export_manifest']
    reconciliation = payload['economic_bundle_reconciliation']
    assert manifest['retention']['policy']['max_feedback_rows'] == 250
    assert reconciliation['node_count'] == 2
    assert reconciliation['consistent'] is True
    assert Path(payload['economic_audit_bundle_entry']['path']).exists()
