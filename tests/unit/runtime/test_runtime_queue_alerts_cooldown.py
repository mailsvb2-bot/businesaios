from __future__ import annotations

from datetime import timedelta

from runtime.queue.job_contract import JobDispatchRequest, normalize_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_alerts import (
    CooldownQueueAlertSink,
    InMemoryQueueAlertSink,
    QueueAlertCooldownPolicy,
    QueueAlertRouter,
)
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOThresholds


def test_queue_alert_cooldown_suppresses_duplicate_delivery_within_window() -> None:
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

    observability = QueueObservabilityRegistry()
    inner_sink = InMemoryQueueAlertSink()
    sink = CooldownQueueAlertSink(inner=inner_sink, cooldown_policy=QueueAlertCooldownPolicy(cooldown_seconds=60))
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=1, max_stale_janitor_age_seconds=999, max_stale_leader_age_seconds=999),
    )
    router = QueueAlertRouter(evaluator=evaluator, observability=observability, sink=sink)

    first = router.evaluate_and_route(tenant_id='t1', queue_name='q1', now=now)
    second = router.evaluate_and_route(tenant_id='t1', queue_name='q1', now=now + timedelta(seconds=10))
    third = router.evaluate_and_route(tenant_id='t1', queue_name='q1', now=now + timedelta(seconds=70))

    assert first and second and third
    delivered = inner_sink.snapshot()
    delivered_pending = [item for item in delivered if item.code == 'pending_jobs_exceeded']
    assert len(delivered_pending) == 2
    # observability still records all derivations, only sink delivery is cooled down
    alert_telemetry = {item.code: item for item in observability.snapshot().alerts}
    assert alert_telemetry['pending_jobs_exceeded'].count == 3


def test_queue_alert_cooldown_publish_report_counts_suppressed_alerts() -> None:
    inner_sink = InMemoryQueueAlertSink()
    sink = CooldownQueueAlertSink(inner=inner_sink, cooldown_policy=QueueAlertCooldownPolicy(cooldown_seconds=60))
    now = normalize_now()
    from runtime.queue.queue_alerts import QueueAlert
    alert = QueueAlert(tenant_id='t1', queue_name='q1', code='pending_jobs_exceeded', severity='error', message='x', created_at=now)
    first = sink.publish_with_report((alert,))
    second = sink.publish_with_report((alert,))
    assert first.published == 1
    assert first.suppressed == 0
    assert second.published == 0
    assert second.suppressed == 1
