from __future__ import annotations

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge
from interfaces.api.business_autonomy_route_handlers import BusinessAutonomyRouteHandlers


def test_route_handlers_can_release_and_retry_quarantine(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    bridge = BusinessAutonomyDelayedOutcomeBridge.default()
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
    })
    handlers = BusinessAutonomyRouteHandlers(stack={'operator_admin_plane': None})
    released = handlers.release_delayed_outcome_quarantine('out_1', released_by='op')
    assert released['released'] is True
    # put it back into quarantine to test retry
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
    })
    retried = handlers.retry_delayed_outcome_quarantine('out_1', retried_by='op')
    assert retried['retried'] is True
