from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_economic_failover_export_import_chain_under_load(tmp_path: Path) -> None:
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=tmp_path / 'runtime_data')
    last_payload = None
    for index in range(5):
        result = orchestrator.run_cycle(
            cycle_input=ClosedLoopCycleInput(
                action={
                    'action_type': 'publish_page',
                    'action_id': f'econ-load-{index}',
                    'decision_id': f'dec-econ-load-{index}',
                    'run_id': f'run-econ-load-{index}',
                    'channel': 'web',
                },
                world_state={'meta': {}},
                execution_receipt={'status': 'executed', 'decision_id': f'dec-econ-load-{index}'},
                feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': [f'page:{index}']}}},
                requested_tier='supervised',
                current_tier='supervised',
            )
        )
        last_payload = result.persisted_memory_evidence
    assert last_payload is not None
    manifest = last_payload['economic_export_manifest']
    reconciliation = last_payload['economic_bundle_reconciliation']
    bundle_entry = last_payload['economic_audit_bundle_entry']
    assert manifest['manifest_version'] == 2
    assert manifest['node_id']
    assert Path(bundle_entry['path']).exists()
    assert reconciliation['quorum_achieved'] is True
    assert reconciliation['quorum_size'] == 2
    assert reconciliation['node_count'] == 2
    assert reconciliation['segment_quorum']['feedback']['support_count'] >= 2
