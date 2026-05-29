from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone, UTC

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
)
from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge


def test_delayed_outcome_sweeper_quarantines_stale_items(tmp_path) -> None:
    bridge = BusinessAutonomyDelayedOutcomeBridge(
        path=tmp_path / 'delayed_outcomes.jsonl',
        state_path=tmp_path / 'delayed_outcome_state.json',
        quarantine_path=tmp_path / 'delayed_outcome_quarantine.jsonl',
    )
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='b1',
            goal_id='g1',
            goal_type='grow',
            metadata={'tenant_id': 'tenant-a', 'planning_horizon': 'now'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
    )
    result = BusinessExecutionResult(
        verdict=ExecutionVerdict.ACCEPTED,
        business_id='b1',
        goal_id='g1',
        execution_id='e1',
        message='accepted',
        metadata={'tenant_id': 'tenant-a'},
    )
    ref = bridge.append_pending(request=request, result=result)
    assert ref is not None
    sweep = bridge.sweep_expired(now=datetime.now(UTC) + timedelta(days=10))
    assert sweep.quarantined_count == 1
    state = json.loads((tmp_path / 'delayed_outcome_state.json').read_text(encoding='utf-8'))
    assert state['active'] == {}
    assert (tmp_path / 'delayed_outcome_quarantine.jsonl').exists()
