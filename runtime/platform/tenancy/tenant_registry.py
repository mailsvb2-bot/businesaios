from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, UTC
from typing import Any, Dict, Iterable, List, Optional, Protocol


class EventStore(Protocol):
    def append(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: dict[str, Any]) -> None: ...
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 5000) -> Iterable[dict[str, Any]]: ...

@dataclass(frozen=True)
class TenantInfo:
    tenant_id: str
    enabled: bool = True

class TenantRegistry:
    EVT_REG = "tenant_registered"
    EVT_DIS = "tenant_disabled"

    def __init__(self, *, store: EventStore, registry_tenant_id: str = "system"):
        self._store = store
        self._registry_tid = registry_tenant_id

    def register(self, *, tenant_id: str, enabled: bool = True) -> None:
        self._store.append(
            tenant_id=self._registry_tid,
            user_id=None,
            event_type=self.EVT_REG,
            payload={"tenant_id": tenant_id, "enabled": bool(enabled), "ts_iso": datetime.now(UTC).isoformat()},
        )

    def disable(self, *, tenant_id: str) -> None:
        self._store.append(
            tenant_id=self._registry_tid,
            user_id=None,
            event_type=self.EVT_DIS,
            payload={"tenant_id": tenant_id, "ts_iso": datetime.now(UTC).isoformat()},
        )

    def list_active_tenants(self, *, limit: int = 5000) -> list[TenantInfo]:
        disabled = set()
        for ev in self._store.latest_events(tenant_id=self._registry_tid, event_type=self.EVT_DIS, limit=limit):
            tid = str((ev.get("payload") or {}).get("tenant_id") or "").strip()
            if tid:
                disabled.add(tid)

        last: dict[str, TenantInfo] = {}
        for ev in self._store.latest_events(tenant_id=self._registry_tid, event_type=self.EVT_REG, limit=limit):
            p = ev.get("payload") or {}
            tid = str(p.get("tenant_id") or "").strip()
            if not tid:
                continue
            last[tid] = TenantInfo(tenant_id=tid, enabled=bool(p.get("enabled", True)))

        res = [info for tid, info in last.items() if info.enabled and tid not in disabled]
        res.sort(key=lambda x: x.tenant_id)
        return res
