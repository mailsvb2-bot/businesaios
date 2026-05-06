from __future__ import annotations

import json

from application.business_autonomy.guarded_service import BusinessAutonomyGuardedService


def test_distributed_state_conflict_state_contains_recovery_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService(business_id='biz-a')
    service._record_distributed_state_conflict(
        tenant_id='tenant-a',
        business_id='biz-a',
        document='business_registry',
        expected_version=1,
        current_version=2,
        recovery_plan='reload_merge_retry',
    )
    state_path = tmp_path / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts_state.json'
    payload = json.loads(state_path.read_text(encoding='utf-8'))
    row = payload['items']['tenant-a:biz-a:business_registry']
    assert row['status'] == 'open'
    assert row['expected_version'] == 1
    assert row['current_version'] == 2
    assert row['recovery_plan'] == 'reload_merge_retry'


def test_distributed_state_conflict_lifecycle_progresses(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService(business_id='biz-a')
    service._record_distributed_state_conflict(
        tenant_id='tenant-a',
        business_id='biz-a',
        document='business_registry',
        expected_version=1,
        current_version=2,
        recovery_plan='reload_merge_retry',
    )
    assert service.acknowledge_distributed_state_conflict(tenant_id='tenant-a', business_id='biz-a', document='business_registry', acknowledged_by='operator') is True
    assert service.resolve_distributed_state_conflict(tenant_id='tenant-a', business_id='biz-a', document='business_registry', resolved_by='operator', resolution_note='merged and resumed') is True
    state_path = tmp_path / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts_state.json'
    payload = json.loads(state_path.read_text(encoding='utf-8'))
    row = payload['items']['tenant-a:biz-a:business_registry']
    assert row['status'] == 'resolved'
    assert row['acknowledged_by'] == 'operator'
    assert row['resolution_note'] == 'merged and resumed'
    assert row['resolved_by'] == 'operator'
