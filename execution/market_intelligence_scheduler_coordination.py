"""Operational scheduler coordination only.

This module coordinates *when* a market-intelligence scheduler instance may run.
It must not add any planning, ranking, or alternative decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from reliability.distributed_lock import DistributedLock, LockLease, build_distributed_lock
from reliability.lease_manager import LeaseManager
from reliability.leader_election import LeaderElection, LeadershipLease

CANON_MARKET_INTELLIGENCE_SCHEDULER_COORDINATION = True

@dataclass(frozen=True)
class SchedulerLeadershipReport:
    tenant_id: str
    owner_id: str
    is_leader: bool
    fencing_token: int | None = None
    expires_at: datetime | None = None
    leadership: LeadershipLease | None = None


class MarketIntelligenceSchedulerCoordination:
    """Thin operational coordination shell.

    Responsibilities:
    - elect exactly one live scheduler leader per tenant/runtime role;
    - acquire/release per-schedule execution leases;
    - expose coordination state for observability.

    Explicit non-responsibilities:
    - no provider ranking;
    - no planning or decision-making;
    - no alternate execution path.
    """

    def __init__(
        self,
        *,
        owner_id: str,
        distributed_lock: DistributedLock | None = None,
        scheduler_leader_election: LeaderElection | None = None,
        schedule_ttl_seconds: int = 300,
        leadership_ttl_seconds: int = 30,
    ) -> None:
        oid = str(owner_id or '').strip()
        if not oid:
            raise ValueError('owner_id is required')
        self._owner_id = oid
        self._distributed_lock = distributed_lock or build_distributed_lock(backend_name='memory')
        self._lease_manager = LeaseManager(lock_provider=self._distributed_lock, default_ttl_seconds=max(1, int(schedule_ttl_seconds)))
        self._leader_election = scheduler_leader_election or LeaderElection(
            lock_backend=self._distributed_lock,
            election_name='market-intelligence-scheduler',
            resource_prefix='market-intelligence-role',
            default_ttl_seconds=max(1, int(leadership_ttl_seconds)),
        )
        self._schedule_ttl_seconds = max(1, int(schedule_ttl_seconds))
        self._leadership: LeadershipLease | None = None

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def distributed_lock(self) -> DistributedLock:
        return self._distributed_lock

    def campaign_or_heartbeat(self, *, tenant_id: str, now: datetime | None = None) -> SchedulerLeadershipReport:
        leadership = self._leader_election.campaign_or_heartbeat(
            tenant_id=tenant_id,
            leader_id=self._owner_id,
            ttl_seconds=self._leader_election._default_ttl_seconds,
            now=now,
        )
        self._leadership = leadership
        return self.snapshot(tenant_id=tenant_id, now=now)

    def is_leader(self, *, tenant_id: str, now: datetime | None = None) -> bool:
        return self.snapshot(tenant_id=tenant_id, now=now).is_leader

    def acquire_schedule_lease(self, *, tenant_id: str, schedule_name: str, now: datetime | None = None) -> LockLease | None:
        resource = self._schedule_resource(schedule_name)
        return self._lease_manager.acquire(
            tenant_id=tenant_id,
            resource=resource,
            owner_id=self._owner_id,
            ttl_seconds=self._schedule_ttl_seconds,
            now=now,
        )

    def release_schedule_lease(self, *, lease: LockLease | None) -> None:
        if lease is None:
            return
        self._lease_manager.release(lease=lease)

    def snapshot(self, *, tenant_id: str, now: datetime | None = None) -> SchedulerLeadershipReport:
        leadership = self._leadership
        if leadership is not None and not self._leader_election.is_leader(leadership=leadership, now=now):
            leadership = None
            self._leadership = None
        return SchedulerLeadershipReport(
            tenant_id=str(tenant_id).strip(),
            owner_id=self._owner_id,
            is_leader=leadership is not None,
            fencing_token=(leadership.fencing_token.as_int() if leadership is not None else None),
            expires_at=(leadership.expires_at if leadership is not None else None),
            leadership=leadership,
        )

    def resign(self) -> None:
        if self._leadership is None:
            return
        self._leader_election.resign(leadership=self._leadership)
        self._leadership = None

    @staticmethod
    def _schedule_resource(schedule_name: str) -> str:
        name = str(schedule_name or '').strip()
        if not name:
            raise ValueError('schedule_name is required')
        return f'market-intelligence-schedule:{name}'


__all__ = [
    'CANON_MARKET_INTELLIGENCE_SCHEDULER_COORDINATION',
    'MarketIntelligenceSchedulerCoordination',
    'SchedulerLeadershipReport',
]
