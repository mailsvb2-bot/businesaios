from __future__ import annotations

import logging
from typing import Any

from core.observability.silent import swallow


def iter_events(event_log: Any):
    store = getattr(event_log, "_store", None)
    if store is None:
        return iter(())
    if hasattr(store, "iter_events"):
        return store.iter_events(tenant_id=str(event_log._tenant.tenant_id), start_ms=0, end_ms=2**63 - 1)
    if hasattr(store, "_events"):
        return iter(store._events)
    return iter(store)


def has_event(event_log: Any, decision_id: str, event_type: str) -> bool:
    did = str(decision_id)
    et = str(event_type)
    store = getattr(event_log, "_store", None)
    logger = logging.getLogger(__name__)
    if store is not None and hasattr(store, "iter_events"):
        try:
            for ev in store.iter_events(tenant_id=str(event_log._tenant.tenant_id), start_ms=0, end_ms=2**63 - 1, event_type=et):
                if str(ev.get("decision_id")) == did:
                    return True
            return False
        except Exception:
            try:
                event_log._metrics.on_backend_fallback_read()
                logger.exception("event_log: iter_events backend failed; falling back")
            except Exception:
                swallow(__name__, "core/events/log_queries.py")

    try:
        for ev in iter_events(event_log):
            if isinstance(ev, dict):
                if str(ev.get("decision_id")) == did and str(ev.get("event_type")) == et:
                    return True
            else:
                if str(getattr(ev, "decision_id", None)) == did and str(getattr(ev, "event_type", None)) == et:
                    return True
    except Exception:
        return False
    return False


def get_events(event_log: Any, decision_id: str, event_type: str) -> list[dict]:
    did = str(decision_id)
    et = str(event_type)
    out: list[dict] = []
    store = getattr(event_log, "_store", None)
    if store is not None and hasattr(store, "iter_events"):
        it = store.iter_events(tenant_id=str(event_log._tenant.tenant_id), start_ms=0, end_ms=2**63 - 1, event_type=et)
        for ev in it:
            if isinstance(ev, dict):
                if str(ev.get("decision_id")) == did and str(ev.get("event_type") or ev.get("type")) == et:
                    out.append(ev)
            else:
                if str(getattr(ev, "decision_id", None)) == did and str(getattr(ev, "event_type", None)) == et:
                    out.append(getattr(ev, "__dict__", {"decision_id": did, "event_type": et}))
        return out

    try:
        for ev in iter_events(event_log):
            if isinstance(ev, dict) and str(ev.get("decision_id")) == did and str(ev.get("event_type") or ev.get("type")) == et:
                out.append(ev)
    except Exception:
        return []
    return out
