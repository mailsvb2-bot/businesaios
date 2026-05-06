from __future__ import annotations

from datetime import timedelta

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator
from runtime.queue.queue_observability import QueueObservabilityRegistry


def _request(job_id: str = "job-1") -> JobDispatchRequest:
    return JobDispatchRequest(
        tenant_id="tenant-1",
        job_id=job_id,
        queue_name="email",
        job_type="send_email",
        payload={"recipient": "a@example.com"},
        dedupe_key=f"dedupe-{job_id}",
    )


def test_janitor_reclaims_expired_claims() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=1, now=now)
    assert claimed is not None

    janitor = JobQueueJanitor(store=store)
    report = janitor.tick(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))

    assert report.reclaimed_expired_claims == 1
    assert report.pending_jobs == 1
    assert report.active_claims == 0


def test_only_leader_runs_janitor_tick() -> None:
    lock = InMemoryDistributedLock()
    election = LeaderElection(lock_backend=lock, election_name="queue-email-janitor", resource_prefix="runtime-queue-role", default_ttl_seconds=30)
    observability = QueueObservabilityRegistry()
    store = InMemoryJobStore()
    now = utc_now()

    leader = QueueLeadershipCoordinator(queue_name="email", role="janitor", leader_election=election, owner_id="janitor-a")
    follower = QueueLeadershipCoordinator(queue_name="email", role="janitor", leader_election=election, owner_id="janitor-b")

    report_a = JobQueueJanitor(store=store, leadership=leader, observability=observability).tick(tenant_id="tenant-1", queue_name="email", now=now)
    report_b = JobQueueJanitor(store=store, leadership=follower, observability=observability).tick(tenant_id="tenant-1", queue_name="email", now=now)

    assert report_a.is_leader is True
    assert report_b.is_leader is False
    snapshot = observability.snapshot()
    assert snapshot.janitors[0].runs == 2
    assert snapshot.janitors[0].skipped_not_leader == 1
