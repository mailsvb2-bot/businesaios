from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from core.growth.autopilot_engine import AutopilotEngine
from core.growth.job_lock_eventstore import EventStoreJobLock


@dataclass(frozen=True)
class AutopilotTarget:
    tenant_id: str
    platform: str
    account_id: str
    notify_chat_id: int | None = None

class AutopilotScheduler:
    def __init__(self, *, lock: EventStoreJobLock, engine: AutopilotEngine, io: Any | None = None, owner: str = "ads_autopilot") -> None:
        self._lock = lock
        self._engine = engine
        self._io = io
        self._owner = owner

    async def tick(self, *, target: AutopilotTarget) -> None:
        lock_key = f"ads_autopilot::{target.tenant_id}::{target.platform}::{target.account_id}"
        lr = self._lock.try_acquire(tenant_id=target.tenant_id, lock_key=lock_key, owner=self._owner)
        if not lr.acquired:
            return
        try:
            out = await self._engine.run(tenant_id=target.tenant_id, platform=target.platform, account_id=target.account_id)
            if self._io is not None and target.notify_chat_id:
                msg = f"🤖 Ads Autopilot: {out.message}\nproposed={out.proposed} applied={out.applied} blocked={out.blocked}"
                await self._io.send(target.notify_chat_id, msg)
        finally:
            self._lock.release(tenant_id=target.tenant_id, lock_key=lock_key, owner=self._owner)
