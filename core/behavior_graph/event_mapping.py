"""Event -> behavior graph mapping.

Heuristic-light and generic: creates a consistent structural view of an event stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable


@dataclass(frozen=True)
class MappedEvent:
    tenant_id: str
    user_id: str
    event_type: str
    timestamp_ms: int
    entities: list[tuple[str, str]]


ENTITY_HINT_KEYS = (
    "product_id",
    "sku",
    "plan_id",
    "tariff",
    "campaign_id",
    "adset_id",
    "ad_id",
    "creative_id",
    "page",
    "screen",
    "utm_campaign",
    "utm_source",
    "utm_medium",
    "feature",
)


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        s = str(v)
    except Exception:
        return ""
    return s.strip()


def map_event(e: dict[str, Any]) -> MappedEvent | None:
    if not isinstance(e, dict):
        return None

    tenant_id = _safe_str(e.get("tenant_id"))
    user_id = _safe_str(e.get("user_id"))
    event_type = _safe_str(e.get("event_type") or e.get("type"))
    try:
        ts = int(e.get("timestamp_ms") or 0)
    except Exception:
        ts = 0

    if not tenant_id or not event_type or not user_id:
        return None

    payload = e.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    entities: list[tuple[str, str]] = []
    for k in ENTITY_HINT_KEYS:
        if k in payload:
            val = _safe_str(payload.get(k))
            if val:
                entities.append((k, val))

    et = _safe_str(payload.get("entity_type"))
    eid = _safe_str(payload.get("entity_id"))
    if et and eid:
        entities.append((et, eid))

    seen = set()
    uniq: list[tuple[str, str]] = []
    for t, k in entities:
        kk = (str(t), str(k))
        if kk in seen:
            continue
        seen.add(kk)
        uniq.append(kk)

    return MappedEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        timestamp_ms=ts,
        entities=uniq,
    )


def map_events(events: Iterable[dict[str, Any]]) -> list[MappedEvent]:
    out: list[MappedEvent] = []
    for e in events:
        me = map_event(e)
        if me is not None:
            out.append(me)
    out.sort(key=lambda x: int(x.timestamp_ms))
    return out
