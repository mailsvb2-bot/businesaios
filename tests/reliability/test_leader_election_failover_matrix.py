from __future__ import annotations

from datetime import timedelta

import pytest

from reliability.distributed_lock import InMemoryDistributedLock, utc_now
from reliability.leader_election import LeaderElection


@pytest.mark.parametrize(('first_ttl', 'takeover_delta_seconds', 'expected_takeover'), [(5, 4, False), (5, 5, True), (5, 6, True)])
def test_leader_failover_matrix(first_ttl: int, takeover_delta_seconds: int, expected_takeover: bool) -> None:
    election = LeaderElection(lock_backend=InMemoryDistributedLock(), election_name='recovery', default_ttl_seconds=5)
    now = utc_now()
    leader1 = election.campaign(tenant_id='tenant-a', leader_id='node-1', ttl_seconds=first_ttl, now=now)
    assert leader1 is not None
    leader2 = election.campaign(tenant_id='tenant-a', leader_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=takeover_delta_seconds))
    if expected_takeover:
        assert leader2 is not None
        assert leader2.leader_id == 'node-2'
        assert leader2.fencing_token.value == 2
    else:
        assert leader2 is None
