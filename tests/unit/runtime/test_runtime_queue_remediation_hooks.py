from __future__ import annotations

from runtime.queue.backpressure_monitor import BackpressureMonitor, StoreTenantPressureReader
from runtime.queue.backpressure_policy import BackpressurePolicy
from runtime.queue.job_contract import JobDispatchRequest, normalize_now
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_health_monitor import QueueHealthMonitor
from runtime.queue.queue_metrics_retention import QueueMetricsRetentionManager
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.queue_remediation_hooks import QueueRemediationCoordinator, QueueRemediationPlanner
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOThresholds
from runtime.queue.tenant_fair_scheduler import TenantFairScheduler


def test_queue_remediation_planner_derives_safe_hooks(tmp_path):
    store = InMemoryJobStore()
    observability = QueueObservabilityRegistry()
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=0, max_stale_janitor_age_seconds=0, max_stale_leader_age_seconds=0),
    )
    dispatcher = JobDispatcher(store=store)
    dispatcher.dispatch(JobDispatchRequest(tenant_id='tenant-a', job_id='job-1', queue_name='ops', job_type='demo', payload={'x': 1}, dedupe_key='a'))
    report = evaluator.evaluate(tenant_id='tenant-a', queue_name='ops')

    plan = QueueRemediationPlanner().plan(report=report, alerts=())

    codes = {hook.code for hook in plan.hooks}
    assert 'run_janitor_tick' in codes
    assert 'apply_metrics_retention' in codes
    assert 'refresh_health_sample' in codes
    assert 'open_queue_history' in codes


def test_queue_remediation_planner_derives_backpressure_and_fairness_hooks(tmp_path):
    store = InMemoryJobStore()
    observability = QueueObservabilityRegistry()
    now = normalize_now()
    for index in range(6):
        store.put(JobDispatchRequest(tenant_id='tenant-a', job_id=f'job-{index}', queue_name='ops', job_type='demo', payload={'x': index}, dedupe_key=f'a-{index}').to_record(now=now))
    evaluator = QueueSLOEvaluator(
        store=store,
        observability=observability,
        thresholds=QueueSLOThresholds(max_pending_jobs=100, max_stale_janitor_age_seconds=999, max_stale_leader_age_seconds=999),
    )
    report = evaluator.evaluate(tenant_id='tenant-a', queue_name='ops', now=now)
    alerts = BackpressureMonitor(
        policy=BackpressurePolicy(queue_soft_limit=4, queue_hard_limit=20, claimed_soft_limit=2, claimed_hard_limit=10),
        fair_scheduler=TenantFairScheduler(default_total_claim_limit=2, max_claims_per_tenant=2, starvation_age_seconds=10),
    ).sample(
        queue_name='ops',
        pressure_reader=StoreTenantPressureReader(store=store, tenant_ids=('tenant-a',), oldest_pending_age_seconds={'tenant-a': 500}),
        now=now,
    ).alerts

    plan = QueueRemediationPlanner().plan(report=report, alerts=alerts)

    codes = {hook.code for hook in plan.hooks}
    assert 'inspect_backpressure' in codes
    assert 'inspect_tenant_fairness' in codes
    assert 'refresh_health_sample' in codes


def test_queue_remediation_coordinator_executes_only_operational_hooks(tmp_path):
    store = InMemoryJobStore()
    observability = QueueObservabilityRegistry()
    evaluator = QueueSLOEvaluator(store=store, observability=observability)
    rollup_store = SqliteQueueMetricsRollupStore(path=tmp_path / 'rollups.sqlite3')
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
    janitor = JobQueueJanitor(store=store, observability=observability)
    retention = QueueMetricsRetentionManager(store=rollup_store)
    coordinator = QueueRemediationCoordinator(
        janitor=janitor,
        metrics_retention=retention,
        health_monitor=monitor,
    )

    dispatcher = JobDispatcher(store=store)
    dispatcher.dispatch(JobDispatchRequest(tenant_id='tenant-a', job_id='job-1', queue_name='ops', job_type='demo', payload={'x': 1}, dedupe_key='a'))

    janitor_result = coordinator.execute(tenant_id='tenant-a', queue_name='ops', hook_code='run_janitor_tick')
    assert janitor_result.executed is True
    assert janitor_result.janitor_report is not None

    retention_result = coordinator.execute(tenant_id='tenant-a', queue_name='ops', hook_code='apply_metrics_retention')
    assert retention_result.executed is True
    assert retention_result.retention_report is not None

    refresh_result = coordinator.execute(tenant_id='tenant-a', queue_name='ops', hook_code='refresh_health_sample')
    assert refresh_result.executed is True
    assert refresh_result.health_report is not None
    assert refresh_result.health_report.backpressure is not None

    review_result = coordinator.execute(tenant_id='tenant-a', queue_name='ops', hook_code='inspect_backpressure')
    assert review_result.executed is False
    assert review_result.reason == 'operator_review_required'
