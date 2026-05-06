from __future__ import annotations

from datetime import timedelta

from runtime.queue.job_contract import JobDispatchRequest, normalize_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_alerts import InMemoryQueueAlertSink, QueueAlertRouter
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOThresholds


def test_queue_alert_router_routes_alerts_into_sink_and_observability() -> None:
    store = InMemoryJobStore()
    now = normalize_now()
    for idx in range(3):
        store.put(
            JobDispatchRequest(
                tenant_id='t1',
                job_id=f'job-{idx}',
                queue_name='q1',
                job_type='demo',
                payload={'i': idx},
                dedupe_key=f'dedupe-{idx}',
            ).to_record(now=now)
        )
    store.mark_dead_letter(tenant_id='t1', job_id='job-0', error='boom', now=now)
    observability = QueueObservabilityRegistry()
    sink = InMemoryQueueAlertSink()
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(
            max_pending_jobs=1,
            max_dead_letter_jobs=0,
            max_stale_janitor_age_seconds=1,
            max_stale_leader_age_seconds=1,
        ),
    )
    router = QueueAlertRouter(evaluator=evaluator, observability=observability, sink=sink)

    alerts = router.evaluate_and_route(tenant_id='t1', queue_name='q1', now=now + timedelta(seconds=10))

    assert alerts
    codes = {item.code for item in alerts}
    assert 'pending_jobs_exceeded' in codes
    assert 'dead_letter_jobs_exceeded' in codes
    assert 'janitor_stale' in codes
    assert 'leadership_stale' in codes
    assert sink.snapshot()
    assert observability.snapshot().alerts
