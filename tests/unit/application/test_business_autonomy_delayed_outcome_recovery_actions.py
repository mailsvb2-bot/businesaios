from __future__ import annotations

from datetime import UTC, datetime, timedelta

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge


def _bridge(tmp_path):
    return BusinessAutonomyDelayedOutcomeBridge(
        path=tmp_path / 'delayed_outcomes.jsonl',
        state_path=tmp_path / 'delayed_outcome_state.json',
        quarantine_path=tmp_path / 'delayed_outcome_quarantine.jsonl',
        sweep_journal_path=tmp_path / 'delayed_outcome_sweep_runs.jsonl',
        action_journal_path=tmp_path / 'delayed_outcome_actions.jsonl',
        action_ledger_path=tmp_path / 'delayed_outcome_action_ledger.jsonl',
    )


def test_release_quarantined_moves_item_back_to_active(tmp_path) -> None:
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
                'expected_ready_at_utc': (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                'metadata': {},
                'quarantine_reason': 'delayed_outcome_stale',
                'quarantined_at_utc': datetime.now(UTC).isoformat(),
            }
        },
    })
    assert bridge.release_quarantined(outcome_id='out_1', released_by='operator') is True
    state = bridge._read_state()
    assert 'out_1' in state['active']
    assert 'out_1' not in state['quarantined']
    assert bridge.list_sweep_runs(limit=1)[0].status == 'released'


def test_retry_quarantined_refreshes_expected_ready_at(tmp_path) -> None:
    bridge = _bridge(tmp_path)
    old = (datetime.now(UTC) - timedelta(days=1)).isoformat()
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
                'expected_ready_at_utc': old,
                'metadata': {'planning_horizon': 'week'},
                'quarantine_reason': 'delayed_outcome_stale',
                'quarantined_at_utc': datetime.now(UTC).isoformat(),
            }
        },
    })
    assert bridge.retry_quarantined(outcome_id='out_1', retried_by='operator') is True
    state = bridge._read_state()
    assert state['active']['out_1']['expected_ready_at_utc'] != old
    assert bridge.list_sweep_runs(limit=1)[0].status == 'retried'


def test_release_writes_admin_action_ledger(tmp_path) -> None:
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
                'expected_ready_at_utc': (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                'metadata': {},
                'quarantine_reason': 'delayed_outcome_stale',
                'quarantined_at_utc': datetime.now(UTC).isoformat(),
            }
        },
    })
    assert bridge.release_quarantined(outcome_id='out_1', released_by='operator', note='manual release') is True
    ledger = (tmp_path / 'delayed_outcome_action_ledger.jsonl').read_text(encoding='utf-8')
    assert '"action_type": "release"' in ledger
    assert '"reason": "manual release"' in ledger
