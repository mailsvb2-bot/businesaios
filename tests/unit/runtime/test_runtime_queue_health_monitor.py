from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from runtime.queue.backpressure_monitor import BackpressureMonitor, StoreTenantPressureReader
from runtime.queue.backpressure_policy import BackpressurePolicy
from runtime.queue.job_contract import JobDispatchRequest, normalize_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_alerts import InMemoryQueueAlertSink, QueueAlertRouter
from runtime.queue.queue_health_monitor import QueueHealthMonitor
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_observability import (
    QueueJanitorTelemetry,
    QueueLeadershipTelemetry,
    QueueObservabilityRegistry,
)
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOThresholds
from runtime.queue.tenant_fair_scheduler import TenantFairScheduler


def test_queue_health_monitor_routes_alerts_and_persists_rollup(tmp_path: Path) -> None:
    now = normalize_now()
    store = InMemoryJobStore()
    for index in range(3):
        store.put(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{index}',
                queue_name='queue-a',
                job_type='demo',
                payload={'index': index},
                dedupe_key=f'dedupe-{index}',
            ).to_record(now=now)
        )
    observability = QueueObservabilityRegistry()
    observability._janitors[('tenant-a', 'queue-a')] = QueueJanitorTelemetry(
        tenant_id='tenant-a',
        queue_name='queue-a',
        last_run_at=now,
    )
    observability._leadership[('tenant-a', 'queue-a', 'janitor')] = QueueLeadershipTelemetry(
        tenant_id='tenant-a',
        queue_name='queue-a',
        role='janitor',
        owner_id='owner-a',
        is_leader=True,
        last_seen_at=now,
    )
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=1, max_active_claims=5, max_dead_letter_jobs=5),
    )
    sink = InMemoryQueueAlertSink()
    router = QueueAlertRouter(evaluator=evaluator, observability=observability, sink=sink)
    rollup_store = SqliteQueueMetricsRollupStore(path=tmp_path / 'queue_rollup.sqlite3')
    monitor = QueueHealthMonitor(evaluator=evaluator, alert_router=router, rollup_store=rollup_store)

    report = monitor.sample(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=1))
    assert report.slo.ok is False
    assert report.slo.status == 'degraded'
    assert len(report.alerts) == 1
    assert report.alerts[0].code == 'pending_jobs_exceeded'
    persisted = rollup_store.summarize(tenant_id='tenant-a', queue_name='queue-a')
    assert persisted is not None
    assert persisted.samples == 1
    assert persisted.total_alert_count == 1
    assert sink.snapshot()[0].code == 'pending_jobs_exceeded'


def test_queue_health_monitor_attaches_backpressure_sample_and_alerts(tmp_path: Path) -> None:
    now = normalize_now()
    store = InMemoryJobStore()
    for index in range(6):
        store.put(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-{index}',
                queue_name='queue-a',
                job_type='send_email',
                payload={'index': index},
                dedupe_key=f'dedupe-{index}',
            ).to_record(now=now)
        )
    observability = QueueObservabilityRegistry()
    observability._janitors[('tenant-a', 'queue-a')] = QueueJanitorTelemetry(
        tenant_id='tenant-a',
        queue_name='queue-a',
        last_run_at=now,
    )
    observability._leadership[('tenant-a', 'queue-a', 'janitor')] = QueueLeadershipTelemetry(
        tenant_id='tenant-a',
        queue_name='queue-a',
        role='janitor',
        owner_id='owner-a',
        is_leader=True,
        last_seen_at=now,
    )
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=100, max_active_claims=5, max_dead_letter_jobs=5),
    )
    rollup_store = SqliteQueueMetricsRollupStore(path=tmp_path / 'queue_rollup_bp.sqlite3')
    bp_monitor = BackpressureMonitor(
        policy=BackpressurePolicy(queue_soft_limit=4, queue_hard_limit=20, claimed_soft_limit=2, claimed_hard_limit=10),
        fair_scheduler=TenantFairScheduler(default_total_claim_limit=2, max_claims_per_tenant=2, starvation_age_seconds=10),
        observability=observability,
    )
    monitor = QueueHealthMonitor(
        evaluator=evaluator,
        rollup_store=rollup_store,
        backpressure_monitor=bp_monitor,
        pressure_reader_factory=lambda tenant_id, queue_name, moment: StoreTenantPressureReader(
            store=store,
            tenant_ids=(tenant_id,),
            oldest_pending_age_seconds={tenant_id: 500},
        ),
    )

    report = monitor.sample(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=1))
    assert report.backpressure is not None
    assert report.backpressure.global_verdict.reason == 'queue_soft_pressure'
    assert any(alert.code == 'queue_soft_pressure' for alert in report.alerts)
    assert any(alert.code == 'tenant_starvation_risk' for alert in report.alerts)
    persisted = rollup_store.summarize(tenant_id='tenant-a', queue_name='queue-a')
    assert persisted is not None
    assert persisted.total_alert_count >= 2


def test_queue_health_monitor_exposes_alert_delivery_report(tmp_path: Path) -> None:
    now = normalize_now()
    store = InMemoryJobStore()
    for index in range(3):
        store.put(
            JobDispatchRequest(
                tenant_id='tenant-a',
                job_id=f'job-delivery-{index}',
                queue_name='queue-a',
                job_type='demo',
                payload={'index': index},
                dedupe_key=f'dedupe-delivery-{index}',
            ).to_record(now=now)
        )
    observability = QueueObservabilityRegistry()
    observability._janitors[('tenant-a', 'queue-a')] = QueueJanitorTelemetry(tenant_id='tenant-a', queue_name='queue-a', last_run_at=now)
    observability._leadership[('tenant-a', 'queue-a', 'janitor')] = QueueLeadershipTelemetry(tenant_id='tenant-a', queue_name='queue-a', role='janitor', owner_id='owner-a', is_leader=True, last_seen_at=now)
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=1, max_active_claims=5, max_dead_letter_jobs=5),
    )
    sink = InMemoryQueueAlertSink()
    router = QueueAlertRouter(evaluator=evaluator, observability=observability, sink=sink)
    monitor = QueueHealthMonitor(evaluator=evaluator, alert_router=router, rollup_store=SqliteQueueMetricsRollupStore(path=tmp_path / 'queue_rollup_delivery.sqlite3'))

    report = monitor.sample(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=1))
    assert report.alert_delivery is not None
    assert report.alert_delivery.attempted == 1
    assert report.alert_delivery.published == 1



def test_queue_health_monitor_routes_from_existing_report_without_double_evaluation(tmp_path: Path) -> None:
    now = normalize_now()
    store = InMemoryJobStore()
    observability = QueueObservabilityRegistry()
    observability._janitors[('tenant-a', 'queue-a')] = QueueJanitorTelemetry(tenant_id='tenant-a', queue_name='queue-a', last_run_at=now)
    observability._leadership[('tenant-a', 'queue-a', 'janitor')] = QueueLeadershipTelemetry(tenant_id='tenant-a', queue_name='queue-a', role='janitor', owner_id='owner-a', is_leader=True, last_seen_at=now)

    class CountingEvaluator(QueueSLOEvaluator):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def evaluate(self, *, tenant_id: str, queue_name: str, now=None):
            self.calls += 1
            return super().evaluate(tenant_id=tenant_id, queue_name=queue_name, now=now)

    evaluator = CountingEvaluator(store=store, observability=observability, thresholds=QueueSLOThresholds())
    router = QueueAlertRouter(evaluator=evaluator, observability=observability, sink=InMemoryQueueAlertSink())
    monitor = QueueHealthMonitor(evaluator=evaluator, alert_router=router, rollup_store=SqliteQueueMetricsRollupStore(path=tmp_path / 'single_eval.sqlite3'))
    monitor.sample(tenant_id='tenant-a', queue_name='queue-a', now=now)
    assert evaluator.calls == 1
