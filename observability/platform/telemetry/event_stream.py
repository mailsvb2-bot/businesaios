from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from observability.platform.telemetry.contracts import AppendOnlyTelemetryStore
from shared.types import ensure_jsonable, new_id


CANON_PLATFORM_TELEMETRY_EVENT_STREAM = True


class TelemetryEventStore(AppendOnlyTelemetryStore):
    """Canonical append-only telemetry event store contract.

    The store remains evidence-only. It must not contain business logic.
    Implementations may expose richer read helpers, but append stays the
    canonical write path.
    """


@dataclass(frozen=True)
class TelemetryEvent:
    event_id: str
    tenant_id: str
    user_id: str | None
    event_type: str
    payload: Dict[str, Any]
    ts_iso: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "payload": ensure_jsonable(self.payload),
            "ts_iso": self.ts_iso,
        }


@dataclass
class InMemoryEventStore:
    _events: List[Dict[str, Any]] = field(default_factory=list)

    def append(self, *, tenant_id: str, user_id: Optional[str], event_type: str, payload: Dict[str, Any]) -> None:
        event = TelemetryEvent(
            event_id=new_id("evt"),
            tenant_id=str(tenant_id),
            user_id=None if user_id is None else str(user_id),
            event_type=str(event_type),
            payload=dict(ensure_jsonable(payload or {})),
            ts_iso=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event.as_dict())

    def latest_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
        limit: int = 2000,
    ) -> Iterable[Dict[str, Any]]:
        tenant = str(tenant_id)
        normalized_user = None if user_id is None else str(user_id)
        accepted_types = self._normalized_event_types(event_type=event_type, event_types=event_types)
        max_items = max(0, int(limit))
        if max_items == 0:
            return []
        out: list[Dict[str, Any]] = []
        for ev in reversed(self._events):
            if ev.get("tenant_id") != tenant:
                continue
            if normalized_user is not None and ev.get("user_id") != normalized_user:
                continue
            if accepted_types is not None and ev.get("event_type") not in accepted_types:
                continue
            out.append(dict(ev))
            if len(out) >= max_items:
                break
        return out

    def latest_event(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
    ) -> Dict[str, Any] | None:
        events = list(
            self.latest_events(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type=event_type,
                event_types=event_types,
                limit=1,
            )
        )
        return events[0] if events else None

    def iter_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> Iterable[Dict[str, Any]]:
        tenant = str(tenant_id)
        normalized_user = None if user_id is None else str(user_id)
        accepted_types = self._normalized_event_types(event_type=event_type, event_types=event_types)
        max_items = None if limit is None else max(0, int(limit))
        if max_items == 0:
            return []
        out: list[Dict[str, Any]] = []
        for ev in self._events:
            if ev.get("tenant_id") != tenant:
                continue
            if normalized_user is not None and ev.get("user_id") != normalized_user:
                continue
            if accepted_types is not None and ev.get("event_type") not in accepted_types:
                continue
            ts_ms = self._ts_iso_to_ms(str(ev.get("ts_iso") or ""))
            if start_ms is not None and ts_ms < int(start_ms):
                continue
            if end_ms is not None and ts_ms > int(end_ms):
                continue
            out.append(dict(ev))
            if max_items is not None and len(out) >= max_items:
                break
        return out

    @staticmethod
    def _normalized_event_types(
        *,
        event_type: str | None,
        event_types: Sequence[str] | None,
    ) -> set[str] | None:
        if event_types:
            return {str(item) for item in event_types}
        if event_type:
            return {str(event_type)}
        return None

    @staticmethod
    def _ts_iso_to_ms(value: str) -> int:
        try:
            dt = datetime.fromisoformat(str(value))
        except Exception:
            return 0
        return int(dt.timestamp() * 1000)


@dataclass(frozen=True)
class EventStoreSink:
    store: TelemetryEventStore

    def emit(self, *, tenant_id: str, user_id: Optional[str], event_type: str, payload: Dict[str, Any]) -> None:
        self.store.append(
            tenant_id=str(tenant_id),
            user_id=None if user_id is None else str(user_id),
            event_type=str(event_type),
            payload=dict(ensure_jsonable(payload or {})),
        )


__all__ = [
    "CANON_PLATFORM_TELEMETRY_EVENT_STREAM",
    "TelemetryEvent",
    "TelemetryEventStore",
    "InMemoryEventStore",
    "EventStoreSink",
]
