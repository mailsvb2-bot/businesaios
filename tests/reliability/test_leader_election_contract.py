from __future__ import annotations

from datetime import timedelta

import pytest

from reliability.distributed_lock import InMemoryDistributedLock, utc_now
from reliability.leader_election import LeaderElection


@pytest.fixture()
def election() -> LeaderElection:
    return LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='runtime-scheduler', default_ttl_seconds=10)


def test_campaign_elects_first_leader(election: LeaderElection) -> None:
    now = utc_now()
    leader = election.campaign(tenant_id='tenant-a', leader_id='node-1', now=now)
    assert leader is not None
    assert leader.leader_id == 'node-1'
    assert leader.fencing_token.value == 1
    assert election.is_leader(leadership=leader, now=now + timedelta(seconds=1)) is True


def test_second_candidate_is_blocked_while_leader_is_live(election: LeaderElection) -> None:
    now = utc_now()
    leader1 = election.campaign(tenant_id='tenant-a', leader_id='node-1', now=now)
    assert leader1 is not None
    leader2 = election.campaign(tenant_id='tenant-a', leader_id='node-2', now=now + timedelta(seconds=1))
    assert leader2 is None


def test_heartbeat_extends_lease_without_changing_fencing_token(election: LeaderElection) -> None:
    now = utc_now()
    leader = election.campaign(tenant_id='tenant-a', leader_id='node-1', now=now)
    assert leader is not None
    renewed = election.heartbeat(leadership=leader, ttl_seconds=20, now=now + timedelta(seconds=5))
    assert renewed.leader_id == 'node-1'
    assert renewed.fencing_token.value == leader.fencing_token.value
    assert renewed.expires_at == now + timedelta(seconds=25)


def test_campaign_or_heartbeat_allows_same_leader_reentry(election: LeaderElection) -> None:
    now = utc_now()
    leader = election.campaign(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=5, now=now)
    assert leader is not None
    continued = election.campaign_or_heartbeat(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=10, now=now + timedelta(seconds=3))
    assert continued is not None
    assert continued.leader_id == 'node-1'
    assert continued.fencing_token.value == leader.fencing_token.value
    assert continued.expires_at == now + timedelta(seconds=13)


def test_failover_after_expiry(election: LeaderElection) -> None:
    now = utc_now()
    leader1 = election.campaign(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=5, now=now)
    assert leader1 is not None
    leader2 = election.campaign(tenant_id='tenant-a', leader_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=6))
    assert leader2 is not None
    assert leader2.leader_id == 'node-2'
    assert leader2.fencing_token.value == 2
    assert election.is_leader(leadership=leader1, now=now + timedelta(seconds=6)) is False
    assert election.is_leader(leadership=leader2, now=now + timedelta(seconds=6)) is True


def test_stale_leader_heartbeat_is_rejected(election: LeaderElection) -> None:
    now = utc_now()
    stale = election.campaign(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=5, now=now)
    assert stale is not None
    current = election.campaign(tenant_id='tenant-a', leader_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=6))
    assert current is not None
    with pytest.raises(PermissionError):
        election.heartbeat(leadership=stale, ttl_seconds=5, now=now + timedelta(seconds=6))


def test_resign_releases_current_leader(election: LeaderElection) -> None:
    now = utc_now()
    leader1 = election.campaign(tenant_id='tenant-a', leader_id='node-1', now=now)
    assert leader1 is not None
    election.resign(leadership=leader1)
    leader2 = election.campaign(tenant_id='tenant-a', leader_id='node-2', now=now + timedelta(seconds=1))
    assert leader2 is not None
    assert leader2.leader_id == 'node-2'
    assert leader2.fencing_token.value == 2


def test_current_leader_returns_none_without_leadership(election: LeaderElection) -> None:
    assert election.current_leader(tenant_id='tenant-a') is None


def test_only_one_live_leader_exists_at_a_time(election: LeaderElection) -> None:
    now = utc_now()
    leader1 = election.campaign(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=10, now=now)
    assert leader1 is not None
    leader2 = election.campaign(tenant_id='tenant-a', leader_id='node-2', ttl_seconds=10, now=now + timedelta(seconds=2))
    assert leader2 is None
    current = election.current_leader(tenant_id='tenant-a')
    assert current is not None
    assert current.leader_id == 'node-1'
    assert current.fencing_token.value == 1
