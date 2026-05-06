from __future__ import annotations

from datetime import timedelta

from reliability.distributed_lock import InMemoryDistributedLock, build_distributed_lock, utc_now
from reliability.leader_election import LeaderElection
from reliability.lease_fencing_token import LeaseFencingToken, assert_fencing_token_progression


def test_build_distributed_lock_defaults_to_memory() -> None:
    lock = build_distributed_lock(backend_name='memory')
    lease = lock.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-a')
    assert lease is not None
    assert lease.fencing_token == 1


def test_leader_election_enforces_single_live_leader() -> None:
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='scheduler')
    now = utc_now()

    leader_a = election.campaign(tenant_id='tenant-a', leader_id='node-a', ttl_seconds=10, now=now)
    blocked = election.campaign(tenant_id='tenant-a', leader_id='node-b', ttl_seconds=10, now=now)
    leader_b = election.campaign(tenant_id='tenant-a', leader_id='node-b', ttl_seconds=10, now=now + timedelta(seconds=11))

    assert leader_a is not None
    assert blocked is None
    assert leader_b is not None
    assert leader_b.fencing_token.as_int() == leader_a.fencing_token.as_int() + 1


def test_fencing_token_progression_rejects_stale_token() -> None:
    current = LeaseFencingToken(3)
    candidate = LeaseFencingToken(2)

    assert candidate.is_stale_against(current=current) is True
    try:
        assert_fencing_token_progression(current=current, candidate=candidate)
    except PermissionError as exc:
        assert 'stale fencing token' in str(exc)
    else:
        raise AssertionError('expected stale fencing token rejection')
