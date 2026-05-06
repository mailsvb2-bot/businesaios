from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.tenancy.normalization import require_tenant_id
from reliability.distributed_lock import LockLease
from reliability.distributed_lock_backend import DistributedLockBackend, ensure_aware
from reliability.lease_fencing_token import LeaseFencingToken

CANON_LEADER_ELECTION = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LeadershipLease:
    tenant_id: str
    election_name: str
    leader_id: str
    resource: str
    fencing_token: LeaseFencingToken
    acquired_at: datetime
    expires_at: datetime

    def is_live(self, *, now: datetime | None = None) -> bool:
        moment = ensure_aware(now or utc_now())
        return moment < ensure_aware(self.expires_at)

    def to_lock_lease(self) -> LockLease:
        lease = LockLease(
            tenant_id=self.tenant_id,
            resource=self.resource,
            owner_id=self.leader_id,
            fencing_token=self.fencing_token.as_int(),
            acquired_at=ensure_aware(self.acquired_at),
            expires_at=ensure_aware(self.expires_at),
        )
        lease.validate()
        return lease


class LeaderElection:
    def __init__(self, *, lock_backend: DistributedLockBackend, election_name: str, resource_prefix: str = 'leader-election', default_ttl_seconds: int = 30) -> None:
        self._lock_backend = lock_backend
        self._election_name = str(election_name or '').strip()
        self._resource_prefix = str(resource_prefix or 'leader-election').strip()
        self._default_ttl_seconds = max(1, int(default_ttl_seconds))
        if not self._election_name:
            raise ValueError('election_name is required')
        if not self._resource_prefix:
            raise ValueError('resource_prefix is required')

    def _resource(self) -> str:
        return f'{self._resource_prefix}:{self._election_name}'

    def _ttl(self, ttl_seconds: int | None) -> int:
        return max(1, int(self._default_ttl_seconds if ttl_seconds is None else ttl_seconds))

    def campaign(self, *, tenant_id: str, leader_id: str, ttl_seconds: int | None = None, now: datetime | None = None) -> LeadershipLease | None:
        tid = require_tenant_id(tenant_id)
        candidate = str(leader_id or '').strip()
        if not candidate:
            raise ValueError('leader_id is required')
        lease = self._lock_backend.acquire(tenant_id=tid, resource=self._resource(), owner_id=candidate, ttl_seconds=self._ttl(ttl_seconds), now=now)
        if lease is None:
            return None
        return self._leadership_from_lease(lease)

    def heartbeat(self, *, leadership: LeadershipLease, ttl_seconds: int | None = None, now: datetime | None = None) -> LeadershipLease:
        lease = self._lock_backend.renew(lease=leadership.to_lock_lease(), ttl_seconds=self._ttl(ttl_seconds), now=now)
        if lease.owner_id != leadership.leader_id:
            raise PermissionError('leadership ownership changed')
        if int(lease.fencing_token) != int(leadership.fencing_token.value):
            raise PermissionError('leadership fencing token changed')
        return self._leadership_from_lease(lease)

    def campaign_or_heartbeat(self, *, tenant_id: str, leader_id: str, ttl_seconds: int | None = None, now: datetime | None = None) -> LeadershipLease | None:
        tid = require_tenant_id(tenant_id)
        candidate = str(leader_id or '').strip()
        if not candidate:
            raise ValueError('leader_id is required')
        existing = self.current_leader(tenant_id=tid)
        if existing is not None and existing.leader_id == candidate:
            return self.heartbeat(leadership=existing, ttl_seconds=ttl_seconds, now=now)
        return self.campaign(tenant_id=tid, leader_id=candidate, ttl_seconds=ttl_seconds, now=now)

    def resign(self, *, leadership: LeadershipLease) -> None:
        current = self._lock_backend.get(tenant_id=leadership.tenant_id, resource=leadership.resource)
        if current is None:
            return
        if current.owner_id != leadership.leader_id or int(current.fencing_token) != int(leadership.fencing_token.value):
            return
        self._lock_backend.release(lease=current)

    def current_leader(self, *, tenant_id: str) -> LeadershipLease | None:
        tid = require_tenant_id(tenant_id)
        lease = self._lock_backend.get(tenant_id=tid, resource=self._resource())
        if lease is None:
            return None
        return self._leadership_from_lease(lease)

    def is_leader(self, *, leadership: LeadershipLease, now: datetime | None = None) -> bool:
        current = self.current_leader(tenant_id=leadership.tenant_id)
        if current is None or not current.is_live(now=now):
            return False
        return current.leader_id == leadership.leader_id and current.resource == leadership.resource and int(current.fencing_token.value) == int(leadership.fencing_token.value)

    def _leadership_from_lease(self, lease: LockLease) -> LeadershipLease:
        lease.validate()
        return LeadershipLease(tenant_id=lease.tenant_id, election_name=self._election_name, leader_id=lease.owner_id, resource=lease.resource, fencing_token=LeaseFencingToken(int(lease.fencing_token)), acquired_at=ensure_aware(lease.acquired_at), expires_at=ensure_aware(lease.expires_at))
