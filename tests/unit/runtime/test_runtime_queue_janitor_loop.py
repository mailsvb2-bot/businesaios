from __future__ import annotations

from datetime import timedelta

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_janitor_loop import JobJanitorLoop
from runtime.queue.job_janitor_supervisor import JobJanitorSupervisor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator
from runtime.queue.queue_retention import QueueRetentionManager, QueueRetentionPolicy


def _request(job_id: str = "job-1") -> JobDispatchRequest:
    return JobDispatchRequest(tenant_id="tenant-1", job_id=job_id, queue_name="email", job_type="send_email", payload={"recipient": "a@example.com"}, dedupe_key=f"dedupe-{job_id}")


def test_janitor_loop_reclaims_and_prunes() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now - timedelta(seconds=10)))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=1, now=now - timedelta(seconds=10))
    assert claimed is not None
    store.reap_expired_claims(tenant_id="tenant-1", queue_name="email", now=now - timedelta(seconds=8))
    claim2 = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=30, now=now - timedelta(seconds=8))
    store.mark_succeeded(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", fencing_token=claim2.lease.fencing_token, now=now - timedelta(seconds=8))

    lock = InMemoryDistributedLock()
    election = LeaderElection(lock_backend=lock, election_name="queue-email-janitor", resource_prefix="runtime-queue-role", default_ttl_seconds=30)
    leadership = QueueLeadershipCoordinator(queue_name="email", role="janitor", leader_election=election, owner_id="janitor-a")
    loop = JobJanitorLoop(
        janitor=JobQueueJanitor(store=store, leadership=leadership),
        tenant_id="tenant-1",
        queue_name="email",
        retention=QueueRetentionManager(store=store, policy=QueueRetentionPolicy(succeeded_ttl_seconds=1, failed_ttl_seconds=999, dead_letter_ttl_seconds=999, cancelled_ttl_seconds=999)),
        idle_sleep_seconds=0.01,
    )
    report = loop.run(max_ticks=1, now=now)
    assert report.ticks == 1
    assert report.retained_removed == 1
    assert store.count(tenant_id="tenant-1", queue_name="email") == 0


def test_janitor_supervisor_runs_and_stops() -> None:
    store = InMemoryJobStore()
    loop = JobJanitorLoop(
        janitor=JobQueueJanitor(store=store),
        tenant_id="tenant-1",
        queue_name="email",
        retention=QueueRetentionManager(store=store),
        idle_sleep_seconds=0.01,
    )
    supervisor = JobJanitorSupervisor(janitor_loop=loop)
    supervisor.start()
    supervisor.request_stop()
    report = supervisor.join(timeout_seconds=2.0)
    assert report is not None
    assert report.stopped_at is not None
