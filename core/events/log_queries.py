from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any


def _event_value(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _supports_keyword(callable_obj: Any, name: str) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
    return name in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _filtered_events(
    events: Iterable[Any],
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_type: str | None,
    event_types: tuple[str, ...],
    user_id: str | None,
    limit: int | None,
):
    allowed_types = set(event_types)
    emitted = 0
    for event in events:
        event_tenant = str(_event_value(event, "tenant_id") or "").strip()
        if event_tenant and event_tenant != tenant_id:
            continue
        timestamp_ms = int(_event_value(event, "timestamp_ms") or 0)
        if timestamp_ms < start_ms or timestamp_ms >= end_ms:
            continue
        if user_id is not None and str(_event_value(event, "user_id")) != user_id:
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
        yield event
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def iter_events(
    event_log: Any,
    *,
    start_ms: int = 0,
    end_ms: int | None = None,
    event_type: str | None = None,
    event_types: Iterable[str] | None = None,
    user_id: str | None = None,
    limit: int | None = None,
):
    store = getattr(event_log, "_store", None)
    if store is None:
        return iter(())
    tenant_id = str(event_log._tenant.tenant_id)
    start = max(0, int(start_ms))
    end = int(end_ms) if end_ms is not None else 2**63 - 1
    allowed_types = tuple(str(item) for item in (event_types or ()) if str(item))
    normalized_type = str(event_type) if event_type is not None else None
    normalized_user = str(user_id) if user_id is not None else None
    normalized_limit = max(1, int(limit)) if limit is not None else None

    iterator = getattr(store, "iter_events", None)
    if callable(iterator):
        kwargs: dict[str, Any] = {
            "tenant_id": tenant_id,
            "start_ms": start,
            "end_ms": end,
        }
        optional = {
            "event_type": normalized_type,
            "event_types": allowed_types or None,
            "user_id": normalized_user,
            "limit": normalized_limit,
        }
        for name, value in optional.items():
            if value is not None and _supports_keyword(iterator, name):
                kwargs[name] = value
        events = iterator(**kwargs)
    elif hasattr(store, "_events"):
        events = iter(store._events)
    else:
        events = iter(store)

    return _filtered_events(
        events,
        tenant_id=tenant_id,
        start_ms=start,
        end_ms=end,
        event_type=normalized_type,
        event_types=allowed_types,
        user_id=normalized_user,
        limit=normalized_limit,
    )


def has_event(event_log: Any, decision_id: str, event_type: str) -> bool:
    did = str(decision_id)
    try:
        return any(
            str(_event_value(event, "decision_id")) == did
            for event in iter_events(event_log, event_type=str(event_type))
        )
    except Exception:
        return False


def get_events(event_log: Any, decision_id: str, event_type: str) -> list[dict]:
    did = str(decision_id)
    out: list[dict] = []
    try:
        for event in iter_events(event_log, event_type=str(event_type)):
            if str(_event_value(event, "decision_id")) != did:
                continue
            if isinstance(event, dict):
                out.append(event)
            else:
                out.append(dict(getattr(event, "__dict__", {})))
    except Exception:
        return []
    return out
