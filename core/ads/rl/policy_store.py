from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from core.events.log import EventLog

_POLICY_EVENT_TYPE = "ads_rl_policy_snapshot@v1"
_POLICY_SOURCE = "ads_rl"
_POLICY_ID_DEFAULT = "ads.rl.policy.v1"


@dataclass(frozen=True)
class PolicySnapshot:
    tenant_id: str
    policy_id: str
    version: int
    created_ms: int
    params: dict


class PolicyStore:
    """Event-sourced RL policy store.

    Canonical source of truth is the event store. Temporary process memory is
    never authoritative; snapshots are reloaded from the append-only log.
    """

    def __init__(self, *, event_store: Any | None = None) -> None:
        self._lock = Lock()
        self._event_store = event_store

    def bind_event_store(self, event_store: Any | None) -> None:
        with self._lock:
            self._event_store = event_store

    def get_latest(self, *, tenant_id: str) -> PolicySnapshot | None:
        tenant_id = str(tenant_id)
        with self._lock:
            return self._load_latest_locked(tenant_id=tenant_id)

    def put(self, *, tenant_id: str, policy_id: str, params: dict) -> PolicySnapshot:
        tenant_id = str(tenant_id)
        now_ms = int(time.time() * 1000)
        with self._lock:
            prev = self._load_latest_locked(tenant_id=tenant_id)
            ver = int(prev.version + 1) if prev else 1
            snap = PolicySnapshot(
                tenant_id=tenant_id,
                policy_id=str(policy_id or _POLICY_ID_DEFAULT),
                version=ver,
                created_ms=now_ms,
                params=dict(params or {}),
            )
            if self._event_store is not None:
                EventLog(self._event_store, tenant=tenant_id).emit(
                    event_type=_POLICY_EVENT_TYPE,
                    source=_POLICY_SOURCE,
                    user_id="system",
                    payload={
                        "policy_id": snap.policy_id,
                        "version": int(snap.version),
                        "created_ms": int(snap.created_ms),
                        "params": dict(snap.params or {}),
                    },
                )
            return snap

    def _load_latest_locked(self, *, tenant_id: str) -> PolicySnapshot | None:
        store = self._event_store
        if store is None or not hasattr(store, "iter_events"):
            return None
        latest: PolicySnapshot | None = None
        for ev in store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=_POLICY_EVENT_TYPE):
            snap = _snapshot_from_event(ev, tenant_id=str(tenant_id))
            if snap is None:
                continue
            if latest is None or _snapshot_order_key(snap) > _snapshot_order_key(latest):
                latest = snap
        return latest


def _snapshot_from_event(event: Any, *, tenant_id: str) -> PolicySnapshot | None:
    if not isinstance(event, dict):
        return None
    payload = event.get("payload") or {}
    version = payload.get("version", event.get("version"))
    created_ms = payload.get("created_ms", event.get("timestamp_ms"))
    policy_id = payload.get("policy_id", event.get("policy_id")) or _POLICY_ID_DEFAULT
    params = payload.get("params", event.get("params")) or {}
    try:
        return PolicySnapshot(
            tenant_id=str(tenant_id),
            policy_id=str(policy_id),
            version=int(version),
            created_ms=int(created_ms),
            params=dict(params or {}),
        )
    except Exception:
        return None


def _snapshot_order_key(snap: PolicySnapshot) -> tuple[int, int]:
    return (int(snap.version), int(snap.created_ms))
