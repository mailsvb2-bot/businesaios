"""Shared read side for business flows: ordered payloads of one event type."""

from __future__ import annotations

import hashlib
from typing import Any

from core.events.read_model_support import best_effort_iter_events

CANON_BUSINESS_FLOW_PROJECTION = True


def flow_payloads(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return tracked flow payloads oldest-first (tenant-wide when user_id is None)."""
    events = best_effort_iter_events(
        event_store=event_store,
        where=f"business_flows.{event_type}",
        tenant_id=str(tenant_id),
        event_types=(str(event_type),),
        start_ms=0,
        end_ms=None,
        user_id=user_id,
    )
    rows = [ev for ev in events if str(ev.get("event_type") or ev.get("type")) == event_type]
    rows.sort(key=lambda ev: int(ev.get("timestamp_ms") or 0))
    out: list[dict[str, Any]] = []
    for ev in rows:
        payload = ev.get("payload")
        if isinstance(payload, dict):
            out.append(dict(payload))
    return out


def stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


__all__ = ["CANON_BUSINESS_FLOW_PROJECTION", "flow_payloads", "stable_id"]
