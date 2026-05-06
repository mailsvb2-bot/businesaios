from __future__ import annotations

import json
from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_economic_restore_import_validation_and_scope_drift_detection(tmp_path: Path) -> None:
    storage_root = tmp_path / 'runtime_data'
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=storage_root)
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={
                'action_type': 'publish_page',
                'action_id': 'econ-scope-1',
                'decision_id': 'dec-econ-scope-1',
                'run_id': 'run-econ-scope-1',
                'channel': 'web',
                'tenant_id': 'tenant-a',
                'business_id': 'biz-a',
                'tenant_tier': 'standard',
                'business_tier': 'standard',
            },
            world_state={'meta': {}},
            execution_receipt={'status': 'executed', 'decision_id': 'dec-econ-scope-1', 'tenant_id': 'tenant-a', 'business_id': 'biz-a'},
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
            requested_tier='supervised',
            current_tier='supervised',
        )
    )
    payload = result.persisted_memory_evidence
    bundle_path = Path(payload['economic_audit_bundle_entry']['path'])
    raw = json.loads(bundle_path.read_text(encoding='utf-8'))
    raw['payload']['export_manifest']['scope'] = {
        'tenant_id': 'tenant-z',
        'business_id': 'biz-a',
        'tenant_tier': 'standard',
        'business_tier': 'standard',
        'profile_name': 'standard',
    }
    bundle_path.write_text(json.dumps(raw), encoding='utf-8')

    recon = orchestrator._build_economic_bundle_reconciliation(
        bundle=payload['economic_audit_bundle'],
        bundle_entry=payload['economic_audit_bundle_entry'],
    )
    assert recon['import_validation']['valid'] is False
    assert any('validation failed' in issue for issue in recon['import_validation']['issues'])
    assert recon['quorum_achieved'] is True
    assert recon['node_count'] == 2
