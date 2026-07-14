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
    """Event-sourced RL policy store backed by one canonical event stream."""

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

    def put(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        params: dict,
        user_id: str = "system",
        decision_id: str = "",
        correlation_id: str = "",
        event_id: str | None = None,
    ) -> PolicySnapshot:
        tenant_id = str(tenant_id)
        now_ms = int(time.time() * 1000)
        with self._lock:
            previous = self._load_latest_locked(tenant_id=tenant_id)
            normalized_policy_id = str(policy_id or _POLICY_ID_DEFAULT)
            if (
                previous is not None
                and event_id is not None
                and previous.policy_id == normalized_policy_id
            ):
                return previous

            version = int(previous.version + 1) if previous else 1
            snapshot = PolicySnapshot(
                tenant_id=tenant_id,
                policy_id=normalized_policy_id,
                version=version,
                created_ms=now_ms,
                params=dict(params or {}),
            )
            if self._event_store is not None:
                try:
                    EventLog(self._event_store, tenant=tenant_id).emit(
                        event_id=event_id,
                        event_type=_POLICY_EVENT_TYPE,
                        source=_POLICY_SOURCE,
                        user_id=str(user_id or "system"),
                        decision_id=str(decision_id) or None,
                        correlation_id=str(correlation_id) or None,
                        payload={
                            "policy_id": snapshot.policy_id,
                            "version": int(snapshot.version),
                            "created_ms": int(snapshot.created_ms),
                            "params": dict(snapshot.params or {}),
                        },
                    )
                except Exception:
                    raced = self._load_latest_locked(tenant_id=tenant_id)
                    if raced is None or raced.policy_id != normalized_policy_id:
                        raise
                    return raced
            return snapshot

    def _load_latest_locked(self, *, tenant_id: str) -> PolicySnapshot | None:
        store = self._event_store
        if store is None or not hasattr(store, "iter_events"):
            return None
        latest: PolicySnapshot | None = None
        for event in store.iter_events(
            tenant_id=str(tenant_id),
            start_ms=0,
            end_ms=None,
            event_type=_POLICY_EVENT_TYPE,
        ):
            snapshot = _snapshot_from_event(event, tenant_id=str(tenant_id))
            if snapshot is None:
                continue
            if latest is None or _snapshot_order_key(snapshot) > _snapshot_order_key(latest):
                latest = snapshot
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


def _snapshot_order_key(snapshot: PolicySnapshot) -> tuple[int, int]:
    return (int(snapshot.version), int(snapshot.created_ms))
