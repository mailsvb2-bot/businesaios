from __future__ import annotations

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.queue_leadership import QueueLeadershipCoordinator


def test_queue_leadership_fails_over_after_resign() -> None:
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='queue-email-janitor', resource_prefix='runtime-queue-role', default_ttl_seconds=30)
    a = QueueLeadershipCoordinator(queue_name='email', role='janitor', leader_election=election, owner_id='owner-a')
    b = QueueLeadershipCoordinator(queue_name='email', role='janitor', leader_election=election, owner_id='owner-b')

    first = a.campaign_or_heartbeat(tenant_id='tenant-1')
    blocked = b.campaign_or_heartbeat(tenant_id='tenant-1')
    assert first.is_leader is True
    assert blocked.is_leader is False

    a.resign()
    after_failover = b.campaign_or_heartbeat(tenant_id='tenant-1')
    assert after_failover.is_leader is True
    assert after_failover.fencing_token == 2
