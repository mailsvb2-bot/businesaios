from __future__ import annotations

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.queue_leadership import QueueLeadershipCoordinator
from runtime.queue.queue_observability import QueueObservabilityRegistry


def test_queue_leadership_allows_only_one_owner() -> None:
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name="queue-email-scheduler", resource_prefix="runtime-queue-role", default_ttl_seconds=30)
    a = QueueLeadershipCoordinator(queue_name="email", role="scheduler", leader_election=election, owner_id="owner-a")
    b = QueueLeadershipCoordinator(queue_name="email", role="scheduler", leader_election=election, owner_id="owner-b")

    report_a = a.campaign_or_heartbeat(tenant_id="tenant-1")
    report_b = b.campaign_or_heartbeat(tenant_id="tenant-1")

    assert report_a.is_leader is True
    assert report_b.is_leader is False
    assert report_a.fencing_token == 1


def test_queue_leadership_records_observability_snapshot() -> None:
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name="queue-email-janitor", resource_prefix="runtime-queue-role", default_ttl_seconds=30)
    observability = QueueObservabilityRegistry()
    coordinator = QueueLeadershipCoordinator(
        queue_name="email",
        role="janitor",
        leader_election=election,
        owner_id="owner-a",
        observability=observability,
    )

    report = coordinator.campaign_or_heartbeat(tenant_id="tenant-1")

    assert report.is_leader is True
    snapshot = observability.snapshot()
    assert snapshot.leadership
    assert snapshot.leadership[0].tenant_id == "tenant-1"
    assert snapshot.leadership[0].queue_name == "email"
