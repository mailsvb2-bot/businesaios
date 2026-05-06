from __future__ import annotations

from application.analytics.fleet_queue_job_bridge import AnalyticsFleetQueueJobBridge
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore


def test_fleet_queue_job_bridge_dispatches_materialization_job():
    bridge = AnalyticsFleetQueueJobBridge(dispatcher=JobDispatcher(store=InMemoryJobStore()))
    verdict = bridge.enqueue_materialization(tenant_id='tenant-1', window_days=14, queue_name='analytics')
    assert verdict['accepted'] is True
    assert verdict['tenant_id'] == 'tenant-1'
    assert verdict['queue_name'] == 'analytics'
    assert verdict['job_id'] == 'analytics-materialize-tenant-1-14'
