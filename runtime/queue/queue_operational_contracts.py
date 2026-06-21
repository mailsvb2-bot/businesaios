from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

CANON_RUNTIME_QUEUE_OPERATIONAL_CONTRACTS = True


@dataclass(frozen=True)
class QueueJanitorReport:
    tenant_id: str
    queue_name: str
    reclaimed_expired_claims: int = 0
    pending_jobs: int = 0
    active_claims: int = 0
    is_leader: bool = True
    leadership_fencing_token: int | None = None
    reason: str = "janitor_tick"
    ran_at: datetime | None = None


@dataclass(frozen=True)
class QueueLeadershipReport:
    tenant_id: str
    queue_name: str
    role: str
    owner_id: str
    is_leader: bool
    fencing_token: int | None = None
    expires_at: datetime | None = None
    leadership: LeadershipLease | None = None


@dataclass(frozen=True)
class QueueSLOReport:
    tenant_id: str
    queue_name: str
    ok: bool
    status: str
    reasons: tuple[str, ...]
    pending_jobs: int
    active_claims: int
    dead_letter_jobs: int
    janitor_stale_seconds: int | None
    leader_stale_seconds: int | None


@dataclass(frozen=True)
class QueueAlert:
    tenant_id: str
    queue_name: str
    code: str
    severity: str
    message: str
    created_at: datetime


__all__ = ["CANON_RUNTIME_QUEUE_OPERATIONAL_CONTRACTS", "QueueAlert", "QueueJanitorReport", "QueueLeadershipReport", "QueueSLOReport"]
