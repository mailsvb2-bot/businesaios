from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.job_contract import JobDispatchRequest, normalize_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_janitor_history_sqlite import SqliteQueueJanitorHistoryStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator


def test_janitor_failover_keeps_operational_role_single_owner(tmp_path: Path) -> None:
    election = LeaderElection(
        lock_backend=InMemoryDistributedLock(),
        election_name='queue-email-janitor',
        resource_prefix='runtime-queue-role',
        default_ttl_seconds=5,
    )
    history = SqliteQueueJanitorHistoryStore(path=tmp_path / 'janitor_history.sqlite3')
    store = InMemoryJobStore()
    now = normalize_now()
    claimed = store.put(
        JobDispatchRequest(
            tenant_id='tenant-a',
            job_id='job-a',
            queue_name='queue-a',
            job_type='demo',
            payload={'value': 1},
            dedupe_key='dedupe-a',
        ).to_record(now=now)
    )
    first_claim = store.claim(tenant_id='tenant-a', job_id=claimed.job_id, owner_id='worker-a', lease_seconds=1, now=now)
    assert first_claim is not None

    leader_a = QueueLeadershipCoordinator(
        queue_name='queue-a',
        role='janitor',
        leader_election=election,
        owner_id='janitor-a',
        history_store=history,
    )
    leader_b = QueueLeadershipCoordinator(
        queue_name='queue-a',
        role='janitor',
        leader_election=election,
        owner_id='janitor-b',
        history_store=history,
    )
    janitor_a = JobQueueJanitor(store=store, leadership=leader_a, history_store=history)
    janitor_b = JobQueueJanitor(store=store, leadership=leader_b, history_store=history)

    report_a = janitor_a.tick(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=2))
    report_b_blocked = janitor_b.tick(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=2))
    assert report_a.is_leader is True
    assert report_a.reclaimed_expired_claims == 1
    assert report_b_blocked.is_leader is False

    leader_a.resign()
    report_b = janitor_b.tick(tenant_id='tenant-a', queue_name='queue-a', now=now + timedelta(seconds=3))
    assert report_b.is_leader is True
    assert report_b.leadership_fencing_token == 2

    leadership_events = history.snapshot_leadership_events(tenant_id='tenant-a', queue_name='queue-a', role='janitor')
    assert any(item.is_leader and item.owner_id.startswith('janitor-a') for item in leadership_events)
    assert any(item.is_leader and item.owner_id.startswith('janitor-b') for item in leadership_events)
