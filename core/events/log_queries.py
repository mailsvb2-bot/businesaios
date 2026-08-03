from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from typing import Any


def _event_value(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def event_timestamp_ms(event: Any) -> int:
    """Return the timestamp domain used by event-store range queries."""

    direct = _event_value(event, "timestamp_ms")
    if direct is not None:
        try:
            return int(direct)
        except (TypeError, ValueError):
            pass
    payload = _event_value(event, "payload")
    if not isinstance(payload, Mapping):
        return 0
    for name in (
        "observed_at_ms",
        "event_time_ms",
        "emitted_at_ms",
        "created_at_ms",
        "assigned_at_ms",
    ):
        try:
            if payload.get(name) is not None:
                return int(payload[name])
        except (TypeError, ValueError):
            continue
    return 0


def event_append_seq(event: Any) -> int:
    """Return the durable store append sequence when exposed by the backend."""

    for name in ("append_seq", "event_sequence", "sequence_id"):
        value = _event_value(event, name)
        try:
            if value is not None:
                return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


def _supports_keyword(callable_obj: Any, name: str) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
    return name in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _tenant_id(event_log: Any) -> str:
    return str(
        getattr(event_log, "tenant_id", "")
        or getattr(getattr(event_log, "_tenant", None), "tenant_id", "")
    )


def direct_latest_append_seq(event_log: Any) -> int | None:
    """Return a cheap backend tail, or None when the backend has no cursor API."""

    store = getattr(event_log, "_store", None)
    owner = store if store is not None else event_log
    getter = getattr(owner, "latest_append_seq", None)
    if not callable(getter):
        return None
    kwargs = (
        {"tenant_id": _tenant_id(event_log)}
        if _supports_keyword(getter, "tenant_id")
        else {}
    )
    return max(0, int(getter(**kwargs) or 0))


def latest_append_seq(event_log: Any) -> int:
    """Return the tenant event-store tail without exposing backend details."""

    direct = direct_latest_append_seq(event_log)
    if direct is not None:
        return direct
    maximum = 0
    for fallback_sequence, event in enumerate(iter_events(event_log), start=1):
        maximum = max(maximum, event_append_seq(event) or fallback_sequence)
    return maximum


def _filtered_events(
    events: Iterable[Any],
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    after_append_seq: int | None,
    event_type: str | None,
    event_types: tuple[str, ...],
    user_id: str | None,
    decision_id: str | None,
    limit: int | None,
):
    allowed_types = set(event_types)
    emitted = 0
    fallback_sequence = 0
    for event in events:
        fallback_sequence += 1
        event_tenant = str(_event_value(event, "tenant_id") or "").strip()
        if event_tenant and event_tenant != tenant_id:
            continue
        append_seq = event_append_seq(event) or fallback_sequence
        if after_append_seq is not None and append_seq <= after_append_seq:
            continue
        timestamp_ms = event_timestamp_ms(event)
        if timestamp_ms < start_ms or timestamp_ms >= end_ms:
            continue
        if user_id is not None and str(_event_value(event, "user_id")) != user_id:
            continue
        if decision_id is not None and str(_event_value(event, "decision_id")) != decision_id:
            continue
        observed_type = str(
            _event_value(event, "event_type")
            or _event_value(event, "type")
            or ""
        )
        if event_type is not None and observed_type != event_type:
            continue
        if allowed_types and observed_type not in allowed_types:
            continue
        if event_append_seq(event) <= 0 and isinstance(event, dict):
            event = {**event, "append_seq": append_seq}
        yield event
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def iter_events(
    event_log: Any,
    *,
    start_ms: int = 0,
    end_ms: int | None = None,
    after_append_seq: int | None = None,
    event_type: str | None = None,
    event_types: Iterable[str] | None = None,
    user_id: str | None = None,
    decision_id: str | None = None,
    limit: int | None = None,
):
    store = getattr(event_log, "_store", None)
    tenant_id = _tenant_id(event_log)
    start = max(0, int(start_ms))
    end = int(end_ms) if end_ms is not None else 2**63 - 1
    after_sequence = (
        max(0, int(after_append_seq))
        if after_append_seq is not None
        else None
    )
    allowed_types = tuple(str(item) for item in (event_types or ()) if str(item))
    normalized_type = str(event_type) if event_type is not None else None
    normalized_user = str(user_id) if user_id is not None else None
    normalized_decision = str(decision_id) if decision_id is not None else None
    normalized_limit = max(1, int(limit)) if limit is not None else None

    iterator = getattr(store, "iter_events", None)
    if not callable(iterator) and store is None:
        iterator = getattr(event_log, "iter_events", None)
    if callable(iterator):
        kwargs: dict[str, Any] = {}
        required = {
            "tenant_id": tenant_id,
            "start_ms": start,
            "end_ms": end,
            "after_append_seq": after_sequence,
        }
        optional = {
            "event_type": normalized_type,
            "event_types": allowed_types or None,
            "user_id": normalized_user,
            "decision_id": normalized_decision,
            "limit": normalized_limit,
        }
        for name, value in {**required, **optional}.items():
            if value is not None and _supports_keyword(iterator, name):
                kwargs[name] = value
        events = iterator(**kwargs)
    elif store is not None and hasattr(store, "_events"):
        events = iter(store._events)
    elif store is not None:
        events = iter(store)
    else:
        events = iter(())

    return _filtered_events(
        events,
        tenant_id=tenant_id,
        start_ms=start,
        end_ms=end,
        after_append_seq=after_sequence,
        event_type=normalized_type,
        event_types=allowed_types,
        user_id=normalized_user,
        decision_id=normalized_decision,
        limit=normalized_limit,
    )


def get_events(event_log: Any, decision_id: str, event_type: str) -> list[dict]:
    store = getattr(event_log, "_store", None)
    if store is None:
        direct_getter = getattr(event_log, "get_events", None)
        if callable(direct_getter):
            try:
                return list(direct_getter(str(decision_id), str(event_type)))
            except Exception:
                pass

    getter = getattr(store, "get_events_for_decision", None)
    if callable(getter):
        try:
            return list(
                getter(
                    tenant_id=_tenant_id(event_log),
                    decision_id=str(decision_id),
                    event_type=str(event_type),
                )
            )
        except Exception:
            pass

    out: list[dict] = []
    try:
        for event in iter_events(
            event_log,
            event_type=str(event_type),
            decision_id=str(decision_id),
        ):
            if isinstance(event, dict):
                out.append(event)
            else:
                out.append(dict(getattr(event, "__dict__", {})))
    except Exception:
        return []
    return out


def has_event(event_log: Any, decision_id: str, event_type: str) -> bool:
    return bool(get_events(event_log, decision_id, event_type))


__all__ = [
    "direct_latest_append_seq",
    "event_append_seq",
    "event_timestamp_ms",
    "get_events",
    "has_event",
    "iter_events",
    "latest_append_seq",
]
