from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge


def _bridge(tmp_path):
    return BusinessAutonomyDelayedOutcomeBridge(
        path=tmp_path / 'delayed_outcomes.jsonl',
        state_path=tmp_path / 'delayed_outcome_state.json',
        quarantine_path=tmp_path / 'delayed_outcome_quarantine.jsonl',
        sweep_journal_path=tmp_path / 'delayed_outcome_sweep_runs.jsonl',
        action_journal_path=tmp_path / 'delayed_outcome_actions.jsonl',
    )


def test_recover_incomplete_run_marks_interrupted_then_sweeps(tmp_path) -> None:
    bridge = _bridge(tmp_path)
    stale = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    bridge._write_state({
        'active': {
            'out_1': {
                'outcome_id': 'out_1',
                'execution_id': 'exec_1',
                'tenant_id': 'tenant-a',
                'business_id': 'biz-a',
                'goal_id': 'goal-a',
                'expected_ready_at_utc': stale,
                'metadata': {'planning_horizon': 'week'},
            }
        },
        'resolved': {},
        'quarantined': {},
        'run_state': {
            'run_id': 'sweep_deadbeef',
            'operation': 'sweep',
            'status': 'in_progress',
            'started_at_utc': datetime.now(timezone.utc).isoformat(),
            'active_before': 1,
            'linked_outcome_ids': ['out_1'],
            'metadata': {'phase': 'mid_sweep'},
        },
    })
    result = bridge.sweep_expired()
    assert result.quarantined_count == 1
    runs = bridge.list_sweep_runs(limit=10)
    assert any(item.status == 'interrupted' and item.run_id == 'sweep_deadbeef' for item in runs)
    assert any(item.status == 'completed' and item.operation == 'sweep' for item in runs)


def test_release_and_retry_link_run_ids(tmp_path) -> None:
    bridge = _bridge(tmp_path)
    bridge._write_state({
        'active': {},
        'resolved': {},
        'quarantined': {
            'out_1': {
                'outcome_id': 'out_1',
                'execution_id': 'exec_1',
                'tenant_id': 'tenant-a',
                'business_id': 'biz-a',
                'goal_id': 'goal-a',
                'expected_ready_at_utc': '2026-01-01T00:00:00+00:00',
                'metadata': {'planning_horizon': 'week'},
                'quarantine_reason': 'delayed_outcome_stale',
                'quarantined_at_utc': '2026-01-02T00:00:00+00:00',
            }
        },
        'run_state': {},
    })
    assert bridge.release_quarantined(outcome_id='out_1', released_by='op', note='ok') is True
    actions = bridge.list_action_runs(limit=10)
    assert actions[0].action == 'release'
    release_run_id = actions[0].run_id
    runs = bridge.list_sweep_runs(limit=10)
    assert any(item.run_id == release_run_id and item.status == 'released' for item in runs)

    state = bridge._read_state()
    state['quarantined'] = {
        'out_1': {
            **state['active'].pop('out_1'),
            'quarantine_reason': 'delayed_outcome_stale',
            'quarantined_at_utc': datetime.now(timezone.utc).isoformat(),
        }
    }
    bridge._write_state(state)
    assert bridge.retry_quarantined(outcome_id='out_1', retried_by='op', planning_horizon='month') is True
    actions = bridge.list_action_runs(limit=10)
    assert actions[0].action == 'retry'
    retry_run_id = actions[0].run_id
    runs = bridge.list_sweep_runs(limit=10)
    assert any(item.run_id == retry_run_id and item.status == 'retried' for item in runs)
    active = bridge._read_state()['active']['out_1']
    assert active['retry_metadata']['run_id'] == retry_run_id


def test_delayed_outcome_state_write_uses_unique_atomic_tempfile(tmp_path) -> None:
    bridge = _bridge(tmp_path)
    bridge._write_state({
        'active': {},
        'resolved': {},
        'quarantined': {},
        'run_state': {'run_id': 'sweep-1', 'status': 'completed'},
    })
    state_path = tmp_path / 'delayed_outcome_state.json'
    assert state_path.exists()
    assert list(state_path.parent.glob('*.tmp')) == []
    payload = json.loads(state_path.read_text(encoding='utf-8'))
    assert payload['run_state']['run_id'] == 'sweep-1'
