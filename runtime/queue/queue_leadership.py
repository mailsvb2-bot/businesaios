"""Leadership binding for queue operational roles.

This layer gates *operational* roles such as janitor or scheduler coordination
through a single leader election lease. It must not invent business intent or
compete with DecisionCore.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from reliability.distributed_lock import InMemoryDistributedLock
from reliability.leader_election import LeaderElection, LeadershipLease
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_operational_contracts import QueueLeadershipReport
from runtime.queue.job_fencing import build_process_scoped_worker_id

CANON_RUNTIME_QUEUE_LEADERSHIP = True

class QueueLeadershipCoordinator:
    def __init__(
        self,
        *,
        queue_name: str,
        role: str,
        leader_election: LeaderElection | None = None,
        ttl_seconds: int = 30,
        owner_id: str | None = None,
        history_store: Any | None = None,
        observability: Any | None = None,
    ) -> None:
        qn = str(queue_name).strip()
        rl = str(role).strip()
        if not qn:
            raise ValueError("queue_name is required")
        if not rl:
            raise ValueError("role is required")
        self._queue_name = qn
        self._role = rl
        self._leader_election = leader_election or LeaderElection(
            lock_backend=InMemoryDistributedLock(),
            election_name=f"queue-{qn}-{rl}",
            resource_prefix="runtime-queue-role",
            default_ttl_seconds=max(1, int(ttl_seconds)),
        )
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._owner_id = build_process_scoped_worker_id(prefix=owner_id or f"queue-{qn}-{rl}")
        self._leadership: LeadershipLease | None = None
        self._history_store = history_store
        self._observability = observability

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def queue_name(self) -> str:
        return self._queue_name

    @property
    def role(self) -> str:
        return self._role

    def campaign_or_heartbeat(self, *, tenant_id: str, now: datetime | None = None) -> QueueLeadershipReport:
        moment = normalize_now(now)
        leadership = self._leader_election.campaign_or_heartbeat(
            tenant_id=tenant_id,
            leader_id=self._owner_id,
            ttl_seconds=self._ttl_seconds,
            now=moment,
        )
        self._leadership = leadership if leadership is not None else None
        report = self.snapshot(tenant_id=tenant_id, now=moment, record=False)
        self._record(report=report, now=moment)
        return report

    def snapshot(self, *, tenant_id: str, now: datetime | None = None, record: bool = True) -> QueueLeadershipReport:
        moment = normalize_now(now)
        leadership = self._leadership
        if leadership is not None and not self._leader_election.is_leader(leadership=leadership, now=moment):
            leadership = None
            self._leadership = None
        report = QueueLeadershipReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=self._queue_name,
            role=self._role,
            owner_id=self._owner_id,
            is_leader=leadership is not None,
            fencing_token=(leadership.fencing_token.as_int() if leadership is not None else None),
            expires_at=(leadership.expires_at if leadership is not None else None),
            leadership=leadership,
        )
        if record:
            self._record(report=report, now=moment)
        return report

    def resign(self) -> None:
        if self._leadership is None:
            return
        self._leader_election.resign(leadership=self._leadership)
        self._leadership = None

    def _record(self, *, report: QueueLeadershipReport, now: datetime) -> None:
        if self._history_store is not None:
            self._history_store.record_leadership(report, seen_at=now)
        if self._observability is not None:
            self._observability.record_leadership(report, now=now)


__all__ = [
    "CANON_RUNTIME_QUEUE_LEADERSHIP",
    "QueueLeadershipCoordinator",
    "QueueLeadershipReport",
]
