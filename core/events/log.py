"""Core-facing event log abstraction.

Ring Spec requires proof events with a strict schema.

Every event MUST contain:
  event_id, user_id, source, event_type, timestamp_ms (UTC), payload,
  decision_id, correlation_id

This module enforces the schema and prevents accidental "loose" events.
Event type in log_types.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Dict, Optional

from core.events.log_emit import normalize_and_validate_event_type
from core.events.log_metrics import EventLogMetrics
from core.events.log_append import normalize_legacy_event
from core.events.log_queries import get_events as _get_events_impl
from core.events.log_queries import has_event as _has_event_impl
from core.events.log_queries import iter_events as _iter_events_impl
import logging

from core.observability.silent import swallow
from config.env_flags import env_bool, env_str
from core.events.log_scope import ensure_ctx_matches_event_log
from core.events.log_store import append_event_dict
from core.events.log_types import Event
from core.events.log_observability import build_system_error_payload, commit_store_if_supported, log_commit_failure
from core.tenancy.scope import TenantScope

_event_log = logging.getLogger(__name__)


def _ensure_legacy_emit_allowed() -> None:
    env = env_str("APP_ENV", env_str("ENV", "dev")).strip().lower()
    strict = env_bool("PRODUCTION_STRICT_TENANT", False)
    if env == "prod" and strict:
        raise RuntimeError("LEGACY_EVENT_WRITE_FORBIDDEN_IN_PROD")


def _mark_legacy_payload(*, payload: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    marked = dict(payload or {})
    marked.setdefault("_legacy_event_path", True)
    marked.setdefault("_legacy_origin_tenant", str(tenant_id))
    return marked


def _emit_legacy_warning(*, tenant_id: str, event_type: str, source: str) -> None:
    try:
        _event_log.warning(
            "event_log: legacy emit path used",
            extra={
                "tenant_id": str(tenant_id),
                "event_type": str(event_type),
                "source": str(source),
            },
        )
    except Exception:
        swallow(__name__, "core/events/log.py")


class EventLog:

    def __init__(self, store, *, tenant: TenantScope | str):
        self._store = store
        scope = tenant if isinstance(tenant, TenantScope) else TenantScope(str(tenant))
        self._tenant = scope
        self._batch_depth = 0
        self._metrics = EventLogMetrics()

    @contextmanager
    def batch(self):
        """Batch writes to the underlying store (if supported).
        Purpose: avoid commit-per-event on SQLite / slow FS.
        Never changes event semantics — only grouping of commits.
        """
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth <= 0:
                self._batch_depth = 0
                try:
                    commit_store_if_supported(self._store)
                except Exception:
                    log_commit_failure()

    def emit(
        self,
        *,
        event_type: str,
        source: str,
        user_id: str,
        payload: Dict[str, Any],
        decision_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp_ms: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> Event:
        et = normalize_and_validate_event_type(event_type)

        evt = Event(

            event_id=event_id or str(uuid.uuid4()),
            user_id=str(user_id),
            source=str(source),
            event_type=str(et),
            timestamp_ms=int(timestamp_ms or int(time.time() * 1000)),
            payload=dict(payload or {}),
            decision_id=str(decision_id) if decision_id is not None else None,
            correlation_id=str(correlation_id) if correlation_id is not None else None,
        )
        self._append_event_dict(asdict(evt))
        self._metrics.on_emit()
        return evt

    def emit_for(self, *, ctx: Any, event_type: str, source: str, user_id: str, payload: Dict[str, Any], decision_id: Optional[str]=None, correlation_id: Optional[str]=None, timestamp_ms: Optional[int]=None, event_id: Optional[str]=None) -> Event:
        ensure_ctx_matches_event_log(ctx=ctx, tenant_id=str(self._tenant.tenant_id))
        return self.emit(event_type=event_type, source=source, user_id=user_id, payload=payload, decision_id=decision_id, correlation_id=correlation_id, timestamp_ms=timestamp_ms, event_id=event_id)





    def emit_legacy(
        self,
        *,
        event_type: str,
        source: str,
        user_id: str,
        payload: Dict[str, Any],
        decision_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp_ms: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> Event:
        """Explicit legacy shim (temporary and tightly fenced).

        Prefer: emit(...) on a tenant-scoped EventLog for the active tenant, or emit_for(ctx=...).

        Canon rule: legacy writes must never silently appear in production-strict
        mode. Outside strict-prod, we preserve compatibility but mark the payload
        so downstream consumers can find and migrate remaining callers.
        """
        _ensure_legacy_emit_allowed()

    # _legacy_event_path marker: legacy emit path used
        marked_payload = _mark_legacy_payload(
            payload=payload,
            tenant_id=str(self._tenant.tenant_id),
        )
        _emit_legacy_warning(
            tenant_id=str(self._tenant.tenant_id),
            event_type=str(event_type),
            source=str(source),
        )

        legacy = EventLog(self._store, tenant="legacy")
        return legacy.emit(
            event_type=event_type,
            source=source,
            user_id=user_id,
            payload=marked_payload,
            decision_id=decision_id,
            correlation_id=correlation_id,
            timestamp_ms=timestamp_ms,
            event_id=event_id,
        )

    def emit_error(self, *, event_type: str, details: dict, source: str = "system", user_id: str = "system") -> Event:
        """Emit a normalized system error event."""
        return self.emit(
            event_type="system_error",
            source=str(source),
            user_id=str(user_id),
            payload=build_system_error_payload(event_type=event_type, details=details),
        )

    def append(self, event: Dict[str, Any]):
        """Compatibility shim.

        If a raw dict is passed, we *normalize* it into the strict schema.
        This prevents silent schema drift.
        """
        et, src, uid, payload, ts = normalize_legacy_event(event)

        self.emit(
            event_type=et,
            source=src,
            user_id=uid,
            payload=payload,
            decision_id=event.get("decision_id"),
            correlation_id=event.get("correlation_id"),
            timestamp_ms=ts,
            event_id=event.get("event_id"),
        )


    def has_event(self, decision_id: str, event_type: str) -> bool:
        """Public proof-event existence check.

        Ring Spec forbids reaching into private storage fields (like event_log._store).
        This method provides a stable API across different backends.
        """

        return _has_event_impl(self, decision_id, event_type)

    def get_events(self, decision_id: str, event_type: str) -> list[dict]:
        """Return all events for a given decision_id and event_type.

        This is the stable API used by reward/proof gating to avoid touching
        private storage fields.
        """

        return _get_events_impl(self, decision_id, event_type)


    def iter_events(self):
        """Iterate events in a backend-agnostic way."""
        return _iter_events_impl(self)

    def _append_event_dict(self, event_dict: Dict[str, Any]) -> None:
        append_event_dict(
            store=self._store,
            batch_depth=self._batch_depth,
            metrics=self._metrics,
            tenant_id=str(self._tenant.tenant_id),
            event_dict=event_dict,
        )

    def __iter__(self):
        return self.iter_events()


    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()
