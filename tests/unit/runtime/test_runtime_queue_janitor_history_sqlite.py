from __future__ import annotations

from pathlib import Path

from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_janitor_history_sqlite import SqliteQueueJanitorHistoryStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator


def test_sqlite_janitor_history_store_persists_janitor_and_leadership(tmp_path: Path) -> None:
    history = SqliteQueueJanitorHistoryStore(path=tmp_path / 'janitor_history.sqlite3')
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='queue-email-janitor', resource_prefix='runtime-queue-role', default_ttl_seconds=30)
    leadership = QueueLeadershipCoordinator(queue_name='email', role='janitor', leader_election=election, owner_id='janitor-a', history_store=history)
    store = InMemoryJobStore()
    janitor = JobQueueJanitor(store=store, leadership=leadership, history_store=history)

    leadership.campaign_or_heartbeat(tenant_id='tenant-1')
    janitor.tick(tenant_id='tenant-1', queue_name='email')

    leadership_rows = history.snapshot_leadership_events(tenant_id='tenant-1', queue_name='email')
    janitor_rows = history.snapshot_janitor_runs(tenant_id='tenant-1', queue_name='email')
    assert len(leadership_rows) >= 1
    assert leadership_rows[-1].is_leader is True
    assert len(janitor_rows) == 1
    assert janitor_rows[0].is_leader is True


def test_sqlite_janitor_history_store_can_purge_old_entries(tmp_path: Path) -> None:
    history = SqliteQueueJanitorHistoryStore(path=tmp_path / 'janitor_history.sqlite3')
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='queue-email-janitor', resource_prefix='runtime-queue-role', default_ttl_seconds=30)
    leadership = QueueLeadershipCoordinator(queue_name='email', role='janitor', leader_election=election, owner_id='janitor-a', history_store=history)
    store = InMemoryJobStore()
    janitor = JobQueueJanitor(store=store, leadership=leadership, history_store=history)

    report = janitor.tick(tenant_id='tenant-1', queue_name='email')
    removed = history.purge_older_than(older_than=report.ran_at)
    assert removed == 0
