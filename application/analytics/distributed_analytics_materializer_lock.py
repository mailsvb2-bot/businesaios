from __future__ import annotations

from dataclasses import dataclass, field

from reliability.distributed_lock_backend import DistributedLockBackend
from reliability.leader_election import LeaderElection, LeadershipLease


@dataclass
class PersistentAnalyticsMaterializerLock:
    lock_backend: DistributedLockBackend
    owner_id: str
    election_name: str = "analytics-materializer"
    resource_prefix: str = "analytics"
    default_ttl_seconds: int = 30
    _election: LeaderElection = field(init=False)

    def __post_init__(self) -> None:
        self._election = LeaderElection(
            lock_backend=self.lock_backend,
            election_name=str(self.election_name),
            resource_prefix=str(self.resource_prefix),
            default_ttl_seconds=int(self.default_ttl_seconds),
        )

    def acquire(self, *, tenant_id: str, ttl_seconds: int | None = None) -> LeadershipLease:
        lease = self._election.campaign(tenant_id=str(tenant_id), leader_id=str(self.owner_id), ttl_seconds=ttl_seconds)
        if lease is None:
            raise RuntimeError("analytics materializer leadership not acquired")
        return lease

    def heartbeat(self, *, leadership: LeadershipLease, ttl_seconds: int | None = None) -> LeadershipLease:
        return self._election.heartbeat(leadership=leadership, ttl_seconds=ttl_seconds)

    def validate(self, *, leadership: LeadershipLease) -> bool:
        return self._election.is_leader(leadership=leadership)

    def release(self, *, leadership: LeadershipLease) -> None:
        self._election.resign(leadership=leadership)
