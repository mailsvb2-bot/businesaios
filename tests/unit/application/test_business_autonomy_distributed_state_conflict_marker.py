from __future__ import annotations

import json

from application.business_autonomy.guarded_service import BusinessAutonomyGuardedService


def test_distributed_state_conflict_marker_is_written(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService(business_id='biz-a')
    service._record_distributed_state_conflict(tenant_id='tenant-a', business_id='biz-a', document='business_registry')
    path = tmp_path / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert rows[-1]['event'] == 'business_autonomy_distributed_state_version_conflict'



def test_repeated_conflict_reopens_lifecycle_and_counts_occurrences(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService('biz-repeat')
    service._record_distributed_state_conflict(
        tenant_id='tenant',
        business_id='biz-repeat',
        document='business_registry',
        expected_version=1,
        current_version=2,
        recovery_plan='reload_merge_retry',
    )
    acknowledged = service.acknowledge_distributed_state_conflict(
        tenant_id='tenant',
        business_id='biz-repeat',
        document='business_registry',
        acknowledged_by='operator-1',
    )
    assert acknowledged is True
    resolved = service.resolve_distributed_state_conflict(
        tenant_id='tenant',
        business_id='biz-repeat',
        document='business_registry',
        resolved_by='operator-1',
        resolution_note='merged',
    )
    assert resolved is True

    service._record_distributed_state_conflict(
        tenant_id='tenant',
        business_id='biz-repeat',
        document='business_registry',
        expected_version=2,
        current_version=3,
        recovery_plan='reload_merge_retry',
    )

    state_path = tmp_path / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts_state.json'
    payload = json.loads(state_path.read_text(encoding='utf-8'))
    row = payload['items']['tenant:biz-repeat:business_registry']
    assert row['status'] == 'open'
    assert row['occurrence_count'] == 2
    assert row['acknowledged_by'] == ''
    assert row['resolved_by'] == ''
    assert row['first_recorded_at_utc']
    assert row['last_recorded_at_utc']


def test_acknowledge_conflict_does_not_duplicate_state_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService('biz-ack')
    service._record_distributed_state_conflict(tenant_id='tenant', business_id='biz-ack', document='business_registry')
    assert service.acknowledge_distributed_state_conflict(tenant_id='tenant', business_id='biz-ack', document='business_registry', acknowledged_by='operator-1') is True
    state_path = tmp_path / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts_state.json'
    payload = json.loads(state_path.read_text(encoding='utf-8'))
    assert list(payload['items']) == ['tenant:biz-ack:business_registry']
    row = payload['items']['tenant:biz-ack:business_registry']
    assert row['status'] == 'acknowledged'
    assert row['acknowledged_by'] == 'operator-1'


def test_distributed_conflict_writer_leaves_no_tmp_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = BusinessAutonomyGuardedService('biz-tmp')
    service._record_distributed_state_conflict(tenant_id='tenant', business_id='biz-tmp', document='business_registry')
    append_dir = tmp_path / 'runtime' / 'distributed' / 'append'
    assert list(append_dir.glob('*.tmp')) == []
