from __future__ import annotations

import json
from pathlib import Path

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def test_orchestrator_marks_invalid_restore_bundle_under_corruption(tmp_path: Path) -> None:
    orchestrator = ClosedLoopOrchestrator(economic_storage_root=tmp_path / 'runtime_data')
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'publish_page', 'action_id': 'econ-1', 'decision_id': 'dec-1', 'run_id': 'run-1', 'channel': 'web'},
            world_state={'meta': {}},
            execution_receipt={'status': 'executed', 'decision_id': 'dec-1'},
            feedback={'evidence': {'router_result': {'verified': True, 'status': 'verified', 'external_refs': ['page:1']}}},
            requested_tier='supervised',
            current_tier='supervised',
        )
    )
    entry = result.persisted_memory_evidence['economic_audit_bundle_entry']
    path = Path(entry['path'])
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['digest'] = 'broken-digest'
    path.write_text(json.dumps(raw), encoding='utf-8')

    reconciliation = orchestrator._build_economic_bundle_reconciliation(
        bundle=result.persisted_memory_evidence['economic_audit_bundle'],
        bundle_entry=entry,
    )
    validation = reconciliation['import_validation']
    assert validation['valid'] is False
    assert validation['status'] == 'invalid'
