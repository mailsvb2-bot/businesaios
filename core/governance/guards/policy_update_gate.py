from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from core.events.log import EventLog

_POLICY_UPDATE_PROPOSED = "policy_update_proposed@v1"
_POLICY_UPDATE_APPROVED = "policy_update_approved@v1"
_POLICY_UPDATE_APPLIED = "policy_update_applied@v1"
_POLICY_UPDATE_SOURCE = "governance_policy_gate"


@dataclass(frozen=True)
class PendingUpdate:
    tenant_id: str
    domain: str
    update_id: str
    created_ms: int
    approved: bool
    payload: dict


class PolicyUpdateGateError(RuntimeError):
    pass


class PolicyUpdateGate:
    """Two-phase policy update gate with event-sourced cooldown/pending state.

    Canonical source of truth is the event store when bound. In-process memory is
    only a hot cache and is never authoritative.
    """

    def __init__(self, *, cooldown_ms: int = 10 * 60 * 1000, event_store: Any | None = None) -> None:
        self._cooldown_ms = int(cooldown_ms)
        if self._cooldown_ms < 0:
            raise ValueError("cooldown_ms must be >= 0")
        self._lock = Lock()
        self._event_store = event_store
        self._pending: dict[str, PendingUpdate] = {}
        self._last_apply_ms: dict[str, int] = {}

    def bind_event_store(self, event_store: Any | None) -> None:
        with self._lock:
            self._event_store = event_store
            self._pending.clear()
            self._last_apply_ms.clear()

    def propose(self, *, tenant_id: str, domain: str, update_id: str, payload: dict, now_ms: int | None = None) -> str:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = int(now_ms or (time.time() * 1000))
        pending = PendingUpdate(
            tenant_id=tenant_id,
            domain=domain,
            update_id=update_id,
            created_ms=now_ms,
            approved=False,
            payload=self._normalize_payload(payload),
        )
        with self._lock:
            self._pending[self._key(tenant_id, domain, update_id)] = pending
            store = self._event_store
        self._emit_event(
            store=store,
            tenant_id=tenant_id,
            event_type=_POLICY_UPDATE_PROPOSED,
            timestamp_ms=now_ms,
            payload=self._event_payload(pending),
            decision_id=update_id,
        )
        return update_id

    def approve(self, *, tenant_id: str, domain: str, update_id: str, now_ms: int | None = None) -> None:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = int(now_ms or (time.time() * 1000))
        k = self._key(tenant_id, domain, update_id)
        with self._lock:
            pending = self._pending.get(k)
            store = self._event_store
        if pending is None:
            pending = self._load_pending(tenant_id=tenant_id, domain=domain, update_id=update_id, store=store)
        if not pending:
            raise PolicyUpdateGateError(f"Unknown update: {k}")
        approved = PendingUpdate(
            tenant_id=pending.tenant_id,
            domain=pending.domain,
            update_id=pending.update_id,
            created_ms=pending.created_ms,
            approved=True,
            payload=dict(pending.payload or {}),
        )
        with self._lock:
            self._pending[k] = approved
        self._emit_event(
            store=store,
            tenant_id=tenant_id,
            event_type=_POLICY_UPDATE_APPROVED,
            timestamp_ms=now_ms,
            payload=self._event_payload(approved),
            decision_id=update_id,
        )

    def claim_for_apply(self, *, tenant_id: str, domain: str, update_id: str, now_ms: int | None = None) -> dict:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = int(now_ms or (time.time() * 1000))
        domain_key = self._domain_key(tenant_id, domain)
        k = self._key(tenant_id, domain, update_id)
        with self._lock:
            pending = self._pending.get(k)
            last = int(self._last_apply_ms.get(domain_key, 0))
            store = self._event_store
        if pending is None:
            pending = self._load_pending(tenant_id=tenant_id, domain=domain, update_id=update_id, store=store)
        if not pending:
            raise PolicyUpdateGateError(f"Unknown update: {k}")
        if not pending.approved:
            raise PolicyUpdateGateError(f"Update not approved: {k}")
        if last <= 0:
            last = self._load_last_apply_ms(tenant_id=tenant_id, domain=domain, store=store)
        if last and now_ms - last < self._cooldown_ms:
            raise PolicyUpdateGateError(f"Cooldown active: wait {self._cooldown_ms - (now_ms - last)} ms")
        with self._lock:
            self._pending.pop(k, None)
            self._last_apply_ms[domain_key] = now_ms
        self._emit_event(
            store=store,
            tenant_id=tenant_id,
            event_type=_POLICY_UPDATE_APPLIED,
            timestamp_ms=now_ms,
            payload=self._event_payload(pending),
            decision_id=update_id,
        )
        return dict(pending.payload)

    @staticmethod
    def _key(tenant_id: str, domain: str, update_id: str) -> str:
        return f"{tenant_id}:{domain}:{update_id}"

    @staticmethod
    def _domain_key(tenant_id: str, domain: str) -> str:
        return f"{tenant_id}:{domain}"

    def _load_pending(self, *, tenant_id: str, domain: str, update_id: str, store: Any | None) -> PendingUpdate | None:
        latest: PendingUpdate | None = None
        latest_state: str | None = None
        latest_ts = -1
        for ev in self._iter_gate_events(store=store, tenant_id=tenant_id):
            if not self._matches_update(ev, domain=domain, update_id=update_id):
                continue
            event_type = str(ev.get("event_type") or "")
            ts = int(ev.get("timestamp_ms") or 0)
            payload = dict(ev.get("payload") or {})
            if event_type == _POLICY_UPDATE_PROPOSED and ts >= latest_ts:
                latest = PendingUpdate(
                    tenant_id=tenant_id,
                    domain=domain,
                    update_id=update_id,
                    created_ms=int(payload.get("created_ms") or ts),
                    approved=False,
                    payload=dict(payload.get("update_payload") or {}),
                )
                latest_state = "proposed"
                latest_ts = ts
            elif event_type == _POLICY_UPDATE_APPROVED and latest is not None and ts >= latest_ts:
                latest = PendingUpdate(
                    tenant_id=tenant_id,
                    domain=domain,
                    update_id=update_id,
                    created_ms=int(payload.get("created_ms") or latest.created_ms),
                    approved=True,
                    payload=dict(payload.get("update_payload") or latest.payload),
                )
                latest_state = "approved"
                latest_ts = ts
            elif event_type == _POLICY_UPDATE_APPLIED and ts >= latest_ts:
                latest = None
                latest_state = "applied"
                latest_ts = ts
        if latest is not None:
            with self._lock:
                self._pending[self._key(tenant_id, domain, update_id)] = latest
        return latest if latest_state in {"proposed", "approved"} else None

    def _load_last_apply_ms(self, *, tenant_id: str, domain: str, store: Any | None) -> int:
        latest = 0
        for ev in self._iter_gate_events(store=store, tenant_id=tenant_id):
            if str(ev.get("event_type") or "") != _POLICY_UPDATE_APPLIED:
                continue
            if str((ev.get("payload") or {}).get("domain") or "") != domain:
                continue
            latest = max(latest, int(ev.get("timestamp_ms") or 0))
        if latest > 0:
            with self._lock:
                self._last_apply_ms[self._domain_key(tenant_id, domain)] = latest
        return latest

    @classmethod
    def _iter_gate_events(cls, *, store: Any | None, tenant_id: str) -> Iterable[dict]:
        iter_events = cls._resolve_iter_events(store)
        if iter_events is None:
            return ()
        events: list[dict] = []
        for event_type in (_POLICY_UPDATE_PROPOSED, _POLICY_UPDATE_APPROVED, _POLICY_UPDATE_APPLIED):
            for ev in iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=event_type):
                if isinstance(ev, dict):
                    events.append(ev)
        return tuple(events)

    @staticmethod
    def _resolve_iter_events(store: Any | None) -> Any | None:
        if store is None:
            return None
        candidate = getattr(store, "iter_events", None)
        return candidate if callable(candidate) else None

    @staticmethod
    def _matches_update(event: dict, *, domain: str, update_id: str) -> bool:
        payload = event.get("payload") or {}
        return str(payload.get("domain") or "") == str(domain) and str(payload.get("update_id") or "") == str(update_id)

    @staticmethod
    def _event_payload(pending: PendingUpdate) -> dict:
        return {
            "tenant_id": str(pending.tenant_id),
            "domain": str(pending.domain),
            "update_id": str(pending.update_id),
            "created_ms": int(pending.created_ms),
            "approved": bool(pending.approved),
            "update_payload": dict(pending.payload or {}),
        }

    @staticmethod
    def _emit_event(*, store: Any | None, tenant_id: str, event_type: str, timestamp_ms: int, payload: dict, decision_id: str) -> None:
        if store is None:
            return
        EventLog(store, tenant=tenant_id).emit(
            event_type=event_type,
            source=_POLICY_UPDATE_SOURCE,
            user_id="system",
            payload=dict(payload or {}),
            decision_id=str(decision_id),
            timestamp_ms=int(timestamp_ms),
        )

    @staticmethod
    def _normalize_token(name: str, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise PolicyUpdateGateError(f"{name} is required")
        return normalized

    @staticmethod
    def _normalize_payload(payload: Any) -> dict:
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise PolicyUpdateGateError("payload must be a mapping")
        return dict(payload)
