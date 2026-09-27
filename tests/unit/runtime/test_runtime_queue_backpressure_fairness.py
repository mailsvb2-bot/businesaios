from __future__ import annotations

from datetime import timedelta

from runtime.queue.backpressure_monitor import BackpressureMonitor
from runtime.queue.backpressure_policy import BackpressurePolicy
from runtime.queue.capability_throttle_policy import CapabilityThrottlePolicy, CapabilityThrottleRule
from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.tenant_fair_scheduler import TenantFairScheduler, TenantQueuePressure
from application.task.registry import DurableTaskRegistry, TaskConflictController, TaskQueuePreemptionCoordinator
from reliability.distributed_lock import InMemoryDistributedLock
from reliability.idempotency_store import InMemoryIdempotencyStore
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _job(*, tenant_id: str, job_id: str, queue_name: str = "email", job_type: str = "send_email", now=None):
    return JobDispatchRequest(
        tenant_id=tenant_id,
        job_id=job_id,
        queue_name=queue_name,
        job_type=job_type,
        payload={"recipient": f"{job_id}@example.com"},
        dedupe_key=f"dedupe-{job_id}",
    ).to_record(now=now)


def test_tenant_fair_scheduler_prioritizes_starving_tenant() -> None:
    scheduler = TenantFairScheduler(default_total_claim_limit=2, max_claims_per_tenant=2, starvation_age_seconds=30)
    report = scheduler.plan_allocations(
        queue_name="email",
        pressures=(
            TenantQueuePressure(tenant_id="tenant-a", queue_name="email", pending_jobs=10, active_claims=0, oldest_pending_age_seconds=600),
            TenantQueuePressure(tenant_id="tenant-b", queue_name="email", pending_jobs=10, active_claims=0, oldest_pending_age_seconds=5),
        ),
    )
    allocs = {item.tenant_id: item for item in report.allocations}
    assert allocs["tenant-a"].claim_limit >= 1
    assert allocs["tenant-a"].starving is True
    assert report.starving_tenants == 1


def test_capability_throttle_preview_is_truthful_until_commit() -> None:
    now = utc_now()
    policy = CapabilityThrottlePolicy(
        rules=(CapabilityThrottleRule(capability="send_email", max_claims_per_window=1, window_seconds=60, burst_claims=0),)
    )
    preview_one = policy.preview(tenant_id="tenant-1", queue_name="email", capability="send_email", requested_claims=1, now=now)
    preview_two = policy.preview(tenant_id="tenant-1", queue_name="email", capability="send_email", requested_claims=1, now=now)
    assert preview_one.allowed is True
    assert preview_two.allowed is True
    used_before, _ = policy.snapshot_window_usage(tenant_id="tenant-1", queue_name="email", capability="send_email", now=now)
    assert used_before == 0
    policy.commit(tenant_id="tenant-1", queue_name="email", capability="send_email", consumed_claims=1, now=now)
    used_after, _ = policy.snapshot_window_usage(tenant_id="tenant-1", queue_name="email", capability="send_email", now=now)
    assert used_after == 1
    blocked = policy.preview(tenant_id="tenant-1", queue_name="email", capability="send_email", requested_claims=1, now=now)
    assert blocked.allowed is False
    assert blocked.reason == "capability_window_exhausted"


def test_backpressure_monitor_reports_fairness_gap_and_global_pressure() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    for idx in range(6):
        store.put(_job(tenant_id="tenant-a", job_id=f"a-{idx}", now=now))
    for idx in range(1):
        store.put(_job(tenant_id="tenant-b", job_id=f"b-{idx}", now=now))
    observability = QueueObservabilityRegistry()
    monitor = BackpressureMonitor(
        policy=BackpressurePolicy(queue_soft_limit=4, queue_hard_limit=20, claimed_soft_limit=2, claimed_hard_limit=10),
        fair_scheduler=TenantFairScheduler(default_total_claim_limit=2, max_claims_per_tenant=2, starvation_age_seconds=10),
        observability=observability,
    )
    report = monitor.sample_from_store(
        store=store,
        queue_name="email",
        tenant_ids=("tenant-a", "tenant-b"),
        total_claim_limit=2,
        oldest_pending_age_seconds={"tenant-a": 500, "tenant-b": 1},
        now=now,
    )
    assert report.global_verdict.reason == "queue_soft_pressure"
    status_by_tenant = {item.tenant_id: item for item in report.tenant_statuses}
    assert status_by_tenant["tenant-a"].fairness_gap >= 4
    assert any(alert.code == "tenant_fairness_gap_high" for alert in report.alerts)
    assert observability.snapshot().alerts


def test_job_scheduler_skips_task_when_canonical_resource_budget_is_exhausted() -> None:
    tenant_id = "tenant-1"
    bundle = TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_actions_per_run=1),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={"actions_per_day": 100.0},
    )
    policies = InMemoryTenantPolicyStore((bundle,))
    budget_guard = TenantExecutionBudgetGuard(
        policy_store=policies,
        quota_guard=TenantQuotaGuard(policy_store=policies),
    )
    store = InMemoryJobStore()
    now = utc_now()
    store.put(
        JobDispatchRequest(
            tenant_id=tenant_id,
            job_id="job-over-budget",
            queue_name="email",
            job_type="send_email",
            payload={"recipient": "x@example.com", "action_count": 2},
            dedupe_key="d-over-budget",
            priority=100,
        ).to_record(now=now)
    )
    store.put(
        JobDispatchRequest(
            tenant_id=tenant_id,
            job_id="job-allowed",
            queue_name="email",
            job_type="send_email",
            payload={"recipient": "ok@example.com", "action_count": 1},
            dedupe_key="d-allowed",
            priority=10,
        ).to_record(now=now)
    )

    batch = JobScheduler(
        store=store,
        tenant_execution_budget_guard=budget_guard,
    ).select_due_jobs(tenant_id=tenant_id, queue_name="email", now=now)

    assert [job.job_id for job in batch.jobs] == ["job-allowed"]
    assert batch.resource_previews["job-over-budget"].allowed is False
    assert batch.resource_previews["job-allowed"].allowed is True


def test_job_scheduler_requests_preemption_and_keeps_high_priority_job_pending() -> None:
    class _Events:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def append_event(self, event: dict) -> None:
            self.events.append(dict(event))

        def iter_events(self, *, tenant_id, start_ms, end_ms=None, user_id=None, event_type=None):
            del end_ms, user_id
            for event in self.events:
                if event.get("tenant_id") == tenant_id and event.get("timestamp_ms", 0) >= start_ms:
                    if event_type is None or event.get("event_type") == event_type:
                        yield dict(event)

    events = _Events()
    tasks = DurableTaskRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    tasks.create(
        tenant_id="tenant-1", business_id="business-1", task_id="low",
        idempotency_key="create-low", priority=20, conflict_keys=("ledger",), occurred_at_ms=1,
    )
    tasks.ready(
        tenant_id="tenant-1", business_id="business-1", task_id="low",
        idempotency_key="ready-low", expected_version=1, occurred_at_ms=2,
    )
    tasks.start(
        tenant_id="tenant-1", business_id="business-1", task_id="low",
        idempotency_key="start-low", expected_version=2, occurred_at_ms=3,
    )
    tasks.create(
        tenant_id="tenant-1", business_id="business-1", task_id="high",
        idempotency_key="create-high", priority=90, conflict_keys=("ledger",), occurred_at_ms=4,
    )
    tasks.ready(
        tenant_id="tenant-1", business_id="business-1", task_id="high",
        idempotency_key="ready-high", expected_version=1, occurred_at_ms=5,
    )
    lock = InMemoryDistributedLock()
    controller = TaskConflictController(distributed_lock=lock)
    held = controller.acquire(
        tenant_id="tenant-1", business_id="business-1", task_id="low",
        conflict_keys=("ledger",), ttl_seconds=60,
    )
    store = InMemoryJobStore()
    now = utc_now()
    store.put(
        JobDispatchRequest(
            tenant_id="tenant-1",
            job_id="job-high",
            queue_name="tasks",
            job_type="work",
            payload={
                "business_id": "business-1",
                "task_id": "high",
                "task_conflict_keys": ["ledger"],
            },
            dedupe_key="high",
            priority=90,
        ).to_record(now=now)
    )
    scheduler = JobScheduler(
        store=store,
        task_preemption_coordinator=TaskQueuePreemptionCoordinator(
            task_registry=tasks,
            distributed_lock=lock,
        ),
    )

    first = scheduler.select_due_jobs(
        tenant_id="tenant-1", queue_name="tasks", now=now
    )
    assert first.jobs == ()
    low = tasks.get(
        tenant_id="tenant-1", business_id="business-1", task_id="low"
    )
    assert low.status.value == "running"
    assert low.preemption_requested_by_task_id == "high"

    paused = tasks.pause(
        tenant_id="tenant-1", business_id="business-1", task_id="low",
        idempotency_key="pause-low", expected_version=low.version, occurred_at_ms=6,
    )
    assert paused.status.value == "paused"
    controller.release(held)

    second = scheduler.select_due_jobs(
        tenant_id="tenant-1", queue_name="tasks", now=now
    )
    assert [job.job_id for job in second.jobs] == ["job-high"]


def test_job_scheduler_filters_jobs_by_capability_preview_and_worker_commit_path() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_job(tenant_id="tenant-1", job_id="job-1", now=now))
    store.put(_job(tenant_id="tenant-1", job_id="job-2", now=now + timedelta(seconds=1)))
    scheduler = JobScheduler(
        store=store,
        capability_throttle_policy=CapabilityThrottlePolicy(
            rules=(CapabilityThrottleRule(capability="send_email", max_claims_per_window=1, window_seconds=60, burst_claims=0),)
        ),
    )
    batch = scheduler.select_due_jobs(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    assert [job.job_id for job in batch.jobs] == ["job-1"]
    scheduler.commit_claimed_job(job=batch.jobs[0], now=now)
    used, _ = scheduler._capability_throttle_policy.snapshot_window_usage(tenant_id="tenant-1", queue_name="email", capability="send_email", now=now)
    assert used == 1



def test_job_scheduler_skips_unresolvable_capability_jobs_fail_closed() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(JobDispatchRequest(tenant_id='tenant-1', job_id='job-bad', queue_name='email', job_type='placeholder', payload={'capability': '   '}, tags=('capability:',), dedupe_key='d-bad').to_record(now=now))
    store.put(_job(tenant_id='tenant-1', job_id='job-good', now=now + timedelta(seconds=1)))
    scheduler = JobScheduler(store=store)
    batch = scheduler.select_due_jobs(tenant_id='tenant-1', queue_name='email', now=now + timedelta(seconds=2))
    assert [job.job_id for job in batch.jobs] == ['job-good']


def test_capability_commit_is_capped_by_window() -> None:
    now = utc_now()
    policy = CapabilityThrottlePolicy(rules=(CapabilityThrottleRule(capability='send_email', max_claims_per_window=1, window_seconds=60, burst_claims=0),))
    committed = policy.commit(tenant_id='tenant-1', queue_name='email', capability='send_email', consumed_claims=5, now=now)
    assert committed == 1
    used, _ = policy.snapshot_window_usage(tenant_id='tenant-1', queue_name='email', capability='send_email', now=now)
    assert used == 1
