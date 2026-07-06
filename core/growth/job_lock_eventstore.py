from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class EventStore(Protocol):
    def append(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: dict) -> None: ...
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 200) -> Iterable[dict]: ...

@dataclass(frozen=True)
class LockResult:
    acquired: bool
    reason: str

class EventStoreJobLock:
    EVT_ACQ = "job_lock_acquired"
    EVT_REL = "job_lock_released"

    def __init__(self, *, store: EventStore, ttl_seconds: int = 300):
        self._store = store
        self._ttl = int(ttl_seconds)

    def try_acquire(self, *, tenant_id: str, lock_key: str, owner: str) -> LockResult:
        now = datetime.now(UTC)
        last_acq = _latest(self._store.latest_events(tenant_id=tenant_id, event_type=self.EVT_ACQ, limit=200), lock_key)
        last_rel = _latest(self._store.latest_events(tenant_id=tenant_id, event_type=self.EVT_REL, limit=200), lock_key)

        if last_acq:
            ts = _parse_iso((last_acq.get("payload") or {}).get("acquired_at_iso"))
            if ts and (now - ts) < timedelta(seconds=self._ttl):
                if last_rel:
                    rts = _parse_iso((last_rel.get("payload") or {}).get("released_at_iso"))
                    if not rts or rts < ts:
                        return LockResult(False, "locked")
                else:
                    return LockResult(False, "locked")

        self._store.append(tenant_id=tenant_id, user_id=None, event_type=self.EVT_ACQ, payload={"lock_key": lock_key, "owner": owner, "acquired_at_iso": now.isoformat(), "ttl_s": self._ttl})
        return LockResult(True, "acquired")

    def release(self, *, tenant_id: str, lock_key: str, owner: str) -> None:
        now = datetime.now(UTC)
        self._store.append(tenant_id=tenant_id, user_id=None, event_type=self.EVT_REL, payload={"lock_key": lock_key, "owner": owner, "released_at_iso": now.isoformat()})

def _latest(events: Iterable[dict], lock_key: str) -> dict | None:
    for ev in events:
        if (ev.get("payload") or {}).get("lock_key") == lock_key:
            return ev
    return None

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
