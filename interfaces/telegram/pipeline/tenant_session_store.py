from __future__ import annotations

"""Telegram tenant session store (in-memory, small TTL).

Purpose:
  - Bind tenant_id to (chat_id,user_id) once a deep-link /start <token>
    was provided.
  - Ensure subsequent callback presses in the same chat are tenant-scoped.

Safety stance:
  - Best-effort. If missing, caller must fallback to safe default
    (env TENANT_ID or explicit token).
  - No persistence: production can swap this via a port.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from core.tenancy.scope import TenantId, as_tenant_id


@dataclass
class _Entry:
    tenant_id: TenantId
    expires_at_ms: int


class TenantSessionStore:
    def __init__(self, *, ttl_s: int = 3600) -> None:
        self._ttl_ms = int(ttl_s) * 1000
        self._items: Dict[Tuple[str, str], _Entry] = {}

    def _gc(self) -> None:
        now = int(time.time() * 1000)
        dead = [k for k, v in self._items.items() if int(v.expires_at_ms) <= now]
        for k in dead:
            self._items.pop(k, None)

    def bind(self, *, chat_id: str, user_id: str, tenant_id: str) -> TenantId:
        self._gc()
        tid = as_tenant_id(tenant_id)
        now = int(time.time() * 1000)
        self._items[(str(chat_id), str(user_id))] = _Entry(tenant_id=tid, expires_at_ms=now + self._ttl_ms)
        return tid

    def get(self, *, chat_id: str, user_id: str) -> Optional[TenantId]:
        self._gc()
        e = self._items.get((str(chat_id), str(user_id)))
        return e.tenant_id if e else None
