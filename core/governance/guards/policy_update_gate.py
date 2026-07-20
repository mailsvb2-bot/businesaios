from __future__ import annotations

import time
from collections.abc import Iterable
from copy import deepcopy
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
    only a hot cache and is never authoritative. State transitions are persisted
    before the hot cache is changed, and a single gate instance serializes claims.
    """

    def __init__(
        self,
        *,
        cooldown_ms: int = 10 * 60 * 1000,
        event_store: Any | None = None,
    ) -> None:
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

    def propose(
        self,
        *,
        tenant_id: str,
        domain: str,
        update_id: str,
        payload: dict,
        now_ms: int | None = None,
    ) -> str:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = self._normalize_now_ms(now_ms)
        pending = PendingUpdate(
            tenant_id=tenant_id,
            domain=domain,
            update_id=update_id,
            created_ms=now_ms,
            approved=False,
            payload=self._normalize_payload(payload),
        )
        key = self._key(tenant_id, domain, update_id)
        with self._lock:
            store = self._event_store
            self._emit_event(
                store=store,
                tenant_id=tenant_id,
                event_type=_POLICY_UPDATE_PROPOSED,
                timestamp_ms=now_ms,
                payload=self._event_payload(pending),
                decision_id=update_id,
            )
            self._pending[key] = pending
        return update_id

    def approve(
        self,
        *,
        tenant_id: str,
        domain: str,
        update_id: str,
        now_ms: int | None = None,
    ) -> None:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = self._normalize_now_ms(now_ms)
        key = self._key(tenant_id, domain, update_id)
        with self._lock:
            pending = self._pending.get(key)
            store = self._event_store
        if pending is None:
            pending = self._load_pending(
                tenant_id=tenant_id,
                domain=domain,
                update_id=update_id,
                store=store,
            )
        if pending is None:
            raise PolicyUpdateGateError(f"Unknown update: {key}")

        with self._lock:
            if self._event_store is not store:
                raise PolicyUpdateGateError("event store changed during approval")
            current = self._pending.get(key)
            if current is None:
                raise PolicyUpdateGateError(f"Unknown update: {key}")
            if current.approved:
                return
            approved = PendingUpdate(
                tenant_id=current.tenant_id,
                domain=current.domain,
                update_id=current.update_id,
                created_ms=current.created_ms,
                approved=True,
                payload=self._copy_payload(current.payload),
            )
            self._emit_event(
                store=store,
                tenant_id=tenant_id,
                event_type=_POLICY_UPDATE_APPROVED,
                timestamp_ms=now_ms,
                payload=self._event_payload(approved),
                decision_id=update_id,
            )
            self._pending[key] = approved

    def claim_for_apply(
        self,
        *,
        tenant_id: str,
        domain: str,
        update_id: str,
        now_ms: int | None = None,
    ) -> dict:
        tenant_id = self._normalize_token("tenant_id", tenant_id)
        domain = self._normalize_token("domain", domain)
        update_id = self._normalize_token("update_id", update_id)
        now_ms = self._normalize_now_ms(now_ms)
        domain_key = self._domain_key(tenant_id, domain)
        key = self._key(tenant_id, domain, update_id)
        with self._lock:
            pending = self._pending.get(key)
            last_apply_ms = int(self._last_apply_ms.get(domain_key, 0))
            store = self._event_store
        if pending is None:
            pending = self._load_pending(
                tenant_id=tenant_id,
                domain=domain,
                update_id=update_id,
                store=store,
            )
        if pending is None:
            raise PolicyUpdateGateError(f"Unknown update: {key}")
        if last_apply_ms <= 0:
            self._load_last_apply_ms(
                tenant_id=tenant_id,
                domain=domain,
                store=store,
            )

        with self._lock:
            if self._event_store is not store:
                raise PolicyUpdateGateError("event store changed during claim")
            current = self._pending.get(key)
            if current is None:
                raise PolicyUpdateGateError(f"Unknown update: {key}")
            if not current.approved:
                raise PolicyUpdateGateError(f"Update not approved: {key}")
            last_apply_ms = int(self._last_apply_ms.get(domain_key, 0))
            if last_apply_ms and now_ms - last_apply_ms < self._cooldown_ms:
                wait_ms = self._cooldown_ms - (now_ms - last_apply_ms)
                raise PolicyUpdateGateError(f"Cooldown active: wait {wait_ms} ms")
            self._emit_event(
                store=store,
                tenant_id=tenant_id,
                event_type=_POLICY_UPDATE_APPLIED,
                timestamp_ms=now_ms,
                payload=self._event_payload(current),
                decision_id=update_id,
            )
            self._pending.pop(key, None)
            self._last_apply_ms[domain_key] = now_ms
            return self._copy_payload(current.payload)

    @staticmethod
    def _key(tenant_id: str, domain: str, update_id: str) -> str:
        return f"{tenant_id}:{domain}:{update_id}"

    @staticmethod
    def _domain_key(tenant_id: str, domain: str) -> str:
        return f"{tenant_id}:{domain}"

    def _load_pending(
        self,
        *,
        tenant_id: str,
        domain: str,
        update_id: str,
        store: Any | None,
    ) -> PendingUpdate | None:
        latest: PendingUpdate | None = None
        latest_state: str | None = None
        latest_ts = -1
        for event in self._iter_gate_events(store=store, tenant_id=tenant_id):
            if not self._matches_update(
                event,
                tenant_id=tenant_id,
                domain=domain,
                update_id=update_id,
            ):
                continue
            event_type = str(event.get("event_type") or "")
            timestamp_ms = self._event_timestamp_ms(event)
            payload = event["payload"]
            if event_type == _POLICY_UPDATE_PROPOSED and timestamp_ms >= latest_ts:
                update_payload = payload.get("update_payload")
                if not isinstance(update_payload, dict):
                    continue
                latest = PendingUpdate(
                    tenant_id=tenant_id,
                    domain=domain,
                    update_id=update_id,
                    created_ms=self._payload_timestamp_ms(
                        payload.get("created_ms"),
                        fallback=timestamp_ms,
                    ),
                    approved=False,
                    payload=self._copy_payload(update_payload),
                )
                latest_state = "proposed"
                latest_ts = timestamp_ms
            elif (
                event_type == _POLICY_UPDATE_APPROVED
                and latest is not None
                and timestamp_ms >= latest_ts
            ):
                update_payload = payload.get("update_payload")
                if update_payload is not None and not isinstance(update_payload, dict):
                    continue
                latest = PendingUpdate(
                    tenant_id=tenant_id,
                    domain=domain,
                    update_id=update_id,
                    created_ms=self._payload_timestamp_ms(
                        payload.get("created_ms"),
                        fallback=latest.created_ms,
                    ),
                    approved=True,
                    payload=self._copy_payload(update_payload or latest.payload),
                )
                latest_state = "approved"
                latest_ts = timestamp_ms
            elif event_type == _POLICY_UPDATE_APPLIED and timestamp_ms >= latest_ts:
                latest = None
                latest_state = "applied"
                latest_ts = timestamp_ms
        if latest is not None:
            with self._lock:
                if self._event_store is store:
                    self._pending[self._key(tenant_id, domain, update_id)] = latest
        return latest if latest_state in {"proposed", "approved"} else None

    def _load_last_apply_ms(
        self,
        *,
        tenant_id: str,
        domain: str,
        store: Any | None,
    ) -> int:
        latest = 0
        for event in self._iter_gate_events(store=store, tenant_id=tenant_id):
            if str(event.get("event_type") or "") != _POLICY_UPDATE_APPLIED:
                continue
            payload = self._event_payload_mapping(event)
            if payload is None or str(payload.get("domain") or "") != domain:
                continue
            latest = max(latest, self._event_timestamp_ms(event))
        if latest > 0:
            with self._lock:
                if self._event_store is store:
                    self._last_apply_ms[self._domain_key(tenant_id, domain)] = latest
        return latest

    @classmethod
    def _iter_gate_events(
        cls,
        *,
        store: Any | None,
        tenant_id: str,
    ) -> Iterable[dict]:
        iter_events = cls._resolve_iter_events(store)
        if iter_events is None:
            return ()
        events: list[dict] = []
        for event_type in (
            _POLICY_UPDATE_PROPOSED,
            _POLICY_UPDATE_APPROVED,
            _POLICY_UPDATE_APPLIED,
        ):
            for event in iter_events(
                tenant_id=str(tenant_id),
                start_ms=0,
                end_ms=None,
                event_type=event_type,
            ):
                if not isinstance(event, dict):
                    continue
                if str(event.get("tenant_id") or "") != str(tenant_id):
                    continue
                if str(event.get("source") or "") != _POLICY_UPDATE_SOURCE:
                    continue
                events.append(event)
        return tuple(events)

    @staticmethod
    def _resolve_iter_events(store: Any | None) -> Any | None:
        if store is None:
            return None
        candidate = getattr(store, "iter_events", None)
        return candidate if callable(candidate) else None

    @staticmethod
    def _matches_update(
        event: dict,
        *,
        tenant_id: str,
        domain: str,
        update_id: str,
    ) -> bool:
        payload = event.get("payload")
        return (
            isinstance(payload, dict)
            and str(event.get("tenant_id") or "") == str(tenant_id)
            and str(event.get("source") or "") == _POLICY_UPDATE_SOURCE
            and str(payload.get("domain") or "") == str(domain)
            and str(payload.get("update_id") or "") == str(update_id)
        )

    @classmethod
    def _event_payload(cls, pending: PendingUpdate) -> dict:
        return {
            "tenant_id": str(pending.tenant_id),
            "domain": str(pending.domain),
            "update_id": str(pending.update_id),
            "created_ms": int(pending.created_ms),
            "approved": bool(pending.approved),
            "update_payload": cls._copy_payload(pending.payload),
        }

    @staticmethod
    def _emit_event(
        *,
        store: Any | None,
        tenant_id: str,
        event_type: str,
        timestamp_ms: int,
        payload: dict,
        decision_id: str,
    ) -> None:
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

    @classmethod
    def _normalize_payload(cls, payload: Any) -> dict:
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise PolicyUpdateGateError("payload must be a mapping")
        return cls._copy_payload(payload)

    @staticmethod
    def _copy_payload(payload: dict) -> dict:
        try:
            return deepcopy(dict(payload or {}))
        except Exception as exc:
            raise PolicyUpdateGateError("payload must be safely copyable") from exc

    @staticmethod
    def _normalize_now_ms(value: int | None) -> int:
        if value is None:
            return int(time.time() * 1000)
        if isinstance(value, bool):
            raise PolicyUpdateGateError("now_ms must be an integer")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise PolicyUpdateGateError("now_ms must be an integer") from exc
        if normalized <= 0:
            raise PolicyUpdateGateError("now_ms must be > 0")
        return normalized

    @staticmethod
    def _event_payload_mapping(event: dict) -> dict | None:
        payload = event.get("payload")
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _event_timestamp_ms(event: dict) -> int:
        value = event.get("timestamp_ms")
        if isinstance(value, bool):
            return 0
        try:
            normalized = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, normalized)

    @staticmethod
    def _payload_timestamp_ms(value: Any, *, fallback: int) -> int:
        if isinstance(value, bool):
            return int(fallback)
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return int(fallback)
        return normalized if normalized > 0 else int(fallback)
