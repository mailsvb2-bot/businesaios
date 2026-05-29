from __future__ import annotations

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.queue_slo import QueueSLOEvaluator, QueueSLOThresholds


def _request(job_id: str) -> JobDispatchRequest:
    return JobDispatchRequest(tenant_id="tenant-1", job_id=job_id, queue_name="email", job_type="send_email", payload={"recipient": "a@example.com"}, dedupe_key=f"dedupe-{job_id}")


def test_queue_slo_reports_stale_control_plane_when_no_telemetry() -> None:
    store = InMemoryJobStore()
    obs = QueueObservabilityRegistry()
    evaluator = QueueSLOEvaluator(store=store, observability=obs, thresholds=QueueSLOThresholds(max_pending_jobs=1, max_active_claims=1, max_dead_letter_jobs=1, max_stale_janitor_age_seconds=1, max_stale_leader_age_seconds=1))
    report = evaluator.evaluate(tenant_id="tenant-1", queue_name="email")
    assert report.ok is False
    assert "janitor_stale" in report.reasons
    assert "leadership_stale" in report.reasons


def test_queue_slo_reports_ok_when_telemetry_is_fresh() -> None:
    now = utc_now()
    store = InMemoryJobStore()
    obs = QueueObservabilityRegistry()
    lock = InMemoryDistributedLock()
    election = LeaderElection(lock_backend=lock, election_name="queue-email-janitor", resource_prefix="runtime-queue-role", default_ttl_seconds=30)
    leadership = QueueLeadershipCoordinator(queue_name="email", role="janitor", leader_election=election, owner_id="janitor-a")
    janitor = JobQueueJanitor(store=store, leadership=leadership, observability=obs)
    janitor.tick(tenant_id="tenant-1", queue_name="email", now=now)
    obs.record_leadership(leadership.snapshot(tenant_id="tenant-1", now=now), now=now)

    evaluator = QueueSLOEvaluator(store=store, observability=obs, thresholds=QueueSLOThresholds(max_pending_jobs=10, max_active_claims=10, max_dead_letter_jobs=10, max_stale_janitor_age_seconds=60, max_stale_leader_age_seconds=60))
    report = evaluator.evaluate(tenant_id="tenant-1", queue_name="email")
    assert report.ok is True
    assert report.reasons == ()



def test_queue_slo_reports_degraded_for_capacity_only() -> None:
    now = utc_now()
    store = InMemoryJobStore()
    obs = QueueObservabilityRegistry()
    lock = InMemoryDistributedLock()
    election = LeaderElection(lock_backend=lock, election_name='queue-email-janitor', resource_prefix='runtime-queue-role', default_ttl_seconds=30)
    leadership = QueueLeadershipCoordinator(queue_name='email', role='janitor', leader_election=election, owner_id='janitor-a')
    janitor = JobQueueJanitor(store=store, leadership=leadership, observability=obs)
    janitor.tick(tenant_id='tenant-1', queue_name='email', now=now)
    obs.record_leadership(leadership.snapshot(tenant_id='tenant-1', now=now), now=now)

    evaluator = QueueSLOEvaluator(store=store, observability=obs, thresholds=QueueSLOThresholds(max_pending_jobs=-1, max_active_claims=10, max_dead_letter_jobs=10, max_stale_janitor_age_seconds=999999, max_stale_leader_age_seconds=999999))
    report = evaluator.evaluate(tenant_id='tenant-1', queue_name='email')
    assert report.ok is False
    assert report.status == 'degraded'
    assert 'pending_jobs_exceeded' in report.reasons


def test_queue_slo_reports_critical_for_stale_control_plane() -> None:
    store = InMemoryJobStore()
    obs = QueueObservabilityRegistry()
    evaluator = QueueSLOEvaluator(store=store, observability=obs, thresholds=QueueSLOThresholds(max_pending_jobs=10, max_active_claims=10, max_dead_letter_jobs=10, max_stale_janitor_age_seconds=0, max_stale_leader_age_seconds=0))
    report = evaluator.evaluate(tenant_id='tenant-1', queue_name='email')
    assert report.ok is False
    assert report.status == 'critical'
    assert 'janitor_stale' in report.reasons
    assert 'leadership_stale' in report.reasons
