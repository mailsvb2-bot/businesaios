from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from contracts.event_store import iter_events_strict
from core.events.log import EventLog

_MATURITY_EVENT_TYPE = "ads_attribution_maturity_snapshot@v1"
_MATURITY_SOURCE = "ads_rl"


@dataclass(frozen=True)
class DecisionMaturity:
    tenant_id: str
    decision_id: str
    created_ms: int
    mature_after_ms: int


class AttributionMaturityGate:
    """Event-sourced gate that prevents instant-learning on immature outcomes.

    Canonical source of truth is the event store. In-process memory is only a
    best-effort hot cache and is never authoritative.
    """

    def __init__(self, *, maturity_window_ms: int = 24 * 60 * 60 * 1000, event_store: Any | None = None) -> None:
        self._window_ms = int(maturity_window_ms)
        self._lock = Lock()
        self._event_store = event_store
        self._cache: dict[str, DecisionMaturity] = {}

    def bind_event_store(self, event_store: Any | None) -> None:
        with self._lock:
            self._event_store = event_store
            self._cache.clear()

    def mark_executed(self, *, tenant_id: str, decision_id: str, now_ms: Optional[int] = None) -> None:
        tenant_id = str(tenant_id)
        decision_id = str(decision_id)
        now_ms = int(now_ms or (time.time() * 1000))
        m = DecisionMaturity(
            tenant_id=tenant_id,
            decision_id=decision_id,
            created_ms=now_ms,
            mature_after_ms=now_ms + self._window_ms,
        )
        with self._lock:
            self._cache[self._cache_key(tenant_id=tenant_id, decision_id=decision_id)] = m
            store = self._event_store
        if store is not None:
            EventLog(store, tenant=tenant_id).emit(
                event_type=_MATURITY_EVENT_TYPE,
                source=_MATURITY_SOURCE,
                user_id="system",
                decision_id=decision_id,
                payload={
                    "decision_id": decision_id,
                    "created_ms": int(m.created_ms),
                    "mature_after_ms": int(m.mature_after_ms),
                    "maturity_window_ms": int(self._window_ms),
                },
            )

    def is_mature(self, *, tenant_id: str, decision_id: str, now_ms: Optional[int] = None) -> bool:
        now_ms = int(now_ms or (time.time() * 1000))
        m = self._get_maturity(tenant_id=str(tenant_id), decision_id=str(decision_id))
        if m is None:
            return False
        return now_ms >= int(m.mature_after_ms)

    def mature_after_ms(self, *, tenant_id: str, decision_id: str) -> Optional[int]:
        m = self._get_maturity(tenant_id=str(tenant_id), decision_id=str(decision_id))
        return int(m.mature_after_ms) if m else None

    def _get_maturity(self, *, tenant_id: str, decision_id: str) -> Optional[DecisionMaturity]:
        key = self._cache_key(tenant_id=tenant_id, decision_id=decision_id)
        with self._lock:
            cached = self._cache.get(key)
            store = self._event_store
        if cached is not None:
            return cached
        loaded = self._load_latest(tenant_id=tenant_id, decision_id=decision_id, store=store)
        if loaded is not None:
            with self._lock:
                self._cache[key] = loaded
        return loaded

    def _load_latest(self, *, tenant_id: str, decision_id: str, store: Any | None) -> Optional[DecisionMaturity]:
        if store is None or not hasattr(store, "iter_events"):
            return None
        latest: Optional[DecisionMaturity] = None
        for ev in iter_events_strict(store, tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=_MATURITY_EVENT_TYPE):
            snap = _maturity_from_event(ev, tenant_id=str(tenant_id), decision_id=str(decision_id))
            if snap is None:
                continue
            if latest is None or _maturity_order_key(snap) > _maturity_order_key(latest):
                latest = snap
        return latest

    @staticmethod
    def _cache_key(*, tenant_id: str, decision_id: str) -> str:
        return f"{tenant_id}:{decision_id}"



def _maturity_from_event(event: Any, *, tenant_id: str, decision_id: str) -> Optional[DecisionMaturity]:
    if not isinstance(event, dict):
        return None
    ev_decision_id = str(event.get("decision_id") or (event.get("payload") or {}).get("decision_id") or "")
    if ev_decision_id != str(decision_id):
        return None
    payload = event.get("payload") or {}
    try:
        created_ms = int(payload.get("created_ms") or event.get("timestamp_ms") or 0)
        mature_after_ms = int(payload.get("mature_after_ms") or 0)
        if mature_after_ms <= 0:
            return None
        return DecisionMaturity(
            tenant_id=str(tenant_id),
            decision_id=str(decision_id),
            created_ms=created_ms,
            mature_after_ms=mature_after_ms,
        )
    except Exception:
        return None



def _maturity_order_key(snap: DecisionMaturity) -> tuple[int, int]:
    return (int(snap.mature_after_ms), int(snap.created_ms))
