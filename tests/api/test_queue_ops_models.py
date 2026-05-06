from __future__ import annotations

from interfaces.api.queue_ops_models import QueueOpsViewResponse, QueueRemediationExecutionResponse


def test_queue_ops_models_as_dict_are_stable() -> None:
    view = QueueOpsViewResponse(
        tenant_id='tenant-a',
        queue_name='ops',
        health={'status': 'healthy'},
        alerts=({'code': 'a'},),
        rollup_summary={'samples': 1},
        remediation_plan={'hooks': ()},
    )
    payload = view.as_dict()
    assert payload['tenant_id'] == 'tenant-a'
    assert payload['alerts'][0]['code'] == 'a'

    execution = QueueRemediationExecutionResponse(
        tenant_id='tenant-a',
        queue_name='ops',
        hook_code='refresh_health_sample',
        executed=True,
        reason='health_sample_refreshed',
        executed_at='2026-01-01T00:00:00+00:00',
        route_recorded=True,
    )
    data = execution.as_dict()
    assert data['route_recorded'] is True
