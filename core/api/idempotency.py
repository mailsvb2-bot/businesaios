from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class IdempotencyKey:
    """Canonical idempotency key (tenant-scoped).

    Safe to log (no secrets).
    """

    tenant_id: TenantId
    key: str

    def normalized(self) -> str:
        k = (self.key or "").strip()
        if not k:
            raise ValueError("EMPTY_IDEMPOTENCY_KEY")
        if len(k) > 256:
            k = hashlib.sha256(k.encode("utf-8")).hexdigest()
        return f"{self.tenant_id}:{k}"


@dataclass(frozen=True)
class IdempotencyRecord:
    status: str  # "in_progress" | "done" | "failed"
    created_at_ms: int
    result: dict[str, Any] | None = None


class IdempotencyStore(Protocol):
    def try_begin(self, *, key: IdempotencyKey, ttl_ms: int) -> bool: ...
    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None: ...
    def mark_done(self, *, key: IdempotencyKey, result: dict[str, Any]) -> None: ...
    def mark_failed(self, *, key: IdempotencyKey, reason: str) -> None: ...


class MemoryIdempotencyStore:
    """In-memory idempotency store (tests/dev)."""

    def __init__(self):
        self._items: dict[str, IdempotencyRecord] = {}

    def _gc(self) -> None:
        now = int(time.time() * 1000)
        to_del = []
        for k, r in self._items.items():
            exp = None
            try:
                exp = int((r.result or {}).get("_expires_at_ms") or 0)
            except Exception:
                exp = None
            if exp and exp < now:
                to_del.append(k)
        for k in to_del:
            self._items.pop(k, None)

    def try_begin(self, *, key: IdempotencyKey, ttl_ms: int) -> bool:
        self._gc()
        nk = key.normalized()
        if nk in self._items:
            return False
        now = int(time.time() * 1000)
        self._items[nk] = IdempotencyRecord(
            status="in_progress",
            created_at_ms=now,
            result={"_expires_at_ms": now + int(ttl_ms)},
        )
        return True

    def get(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        self._gc()
        return self._items.get(key.normalized())

    def mark_done(self, *, key: IdempotencyKey, result: dict[str, Any]) -> None:
        nk = key.normalized()
        r = self._items.get(nk)
        now = int(time.time() * 1000)
        if r is None:
            self._items[nk] = IdempotencyRecord(status="done", created_at_ms=now, result=dict(result))
        else:
            self._items[nk] = IdempotencyRecord(status="done", created_at_ms=r.created_at_ms, result=dict(result))

    def mark_failed(self, *, key: IdempotencyKey, reason: str) -> None:
        nk = key.normalized()
        r = self._items.get(nk)
        now = int(time.time() * 1000)
        res = {"error": (reason or "FAILED").strip()[:200]}
        if r is None:
            self._items[nk] = IdempotencyRecord(status="failed", created_at_ms=now, result=res)
        else:
            self._items[nk] = IdempotencyRecord(status="failed", created_at_ms=r.created_at_ms, result=res)


class IdempotentEndpoint:
    """Execute a function once per idempotency key."""

    def __init__(self, store: IdempotencyStore, *, ttl_ms: int = 10 * 60 * 1000):
        self._store = store
        self._ttl_ms = int(ttl_ms)

    def call(self, *, key: IdempotencyKey, fn):
        if self._store.try_begin(key=key, ttl_ms=self._ttl_ms):
            try:
                out = fn()
            except Exception as e:
                self._store.mark_failed(key=key, reason=type(e).__name__)
                raise
            self._store.mark_done(key=key, result={"ok": True})
            return out

        rec = self._store.get(key=key)
        if rec and rec.status == "done":
            return {"ok": True, "idempotent_replay": True}
        if rec and rec.status == "failed":
            return {
                "ok": False,
                "idempotent_replay": True,
                "error": (rec.result or {}).get("error"),
            }
        return {"ok": False, "error": "IDEMPOTENCY_IN_PROGRESS"}
