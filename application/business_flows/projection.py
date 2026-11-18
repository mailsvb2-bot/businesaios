"""Shared read side for business flows: ordered payloads of one event type."""

from __future__ import annotations

import hashlib
from typing import Any

from core.events.read_model_support import best_effort_iter_events

CANON_BUSINESS_FLOW_PROJECTION = True


LEGACY_ATTRIBUTED = "legacy_leads_attributed"


def legacy_quarantine_enabled() -> bool:
    from config.env_flags import env_bool

    return env_bool("BAI_SALES_LEGACY_QUARANTINE_ENABLED", False)


def legacy_attribution(payloads: list[dict[str, Any]]) -> dict[str, str]:
    """Migration evidence from the existing signed sales_pipeline event owner only.

    A conflicting business claim is never interpreted as a successful transfer.
    """
    result: dict[str, str] = {}
    conflicting: set[str] = set()
    for fact in payloads:
        if fact.get("step") != LEGACY_ATTRIBUTED:
            continue
        lead, business = str(fact.get("lead_id") or "").strip(), str(fact.get("business_id") or "").strip()
        if not lead or not business:
            continue
        if lead in result and result[lead] != business:
            conflicting.add(lead)
        else:
            result[lead] = business
    return {lead: business for lead, business in result.items() if lead not in conflicting}


def legacy_quarantine(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Owner audit shows only opaque IDs/counts; no pre-D2 customer PII."""
    attributed = legacy_attribution(payloads)
    unscoped: dict[str, int] = {}
    for fact in payloads:
        if fact.get("step") == LEGACY_ATTRIBUTED or fact.get("business_id"):
            continue
        lead = str(fact.get("lead_id") or "").strip()
        if lead and lead not in attributed:
            unscoped[lead] = unscoped.get(lead, 0) + 1
    return [{"lead_id": lead, "facts": count} for lead, count in sorted(unscoped.items())]




def flow_rows(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    user_id: str | None = None,
    business_id: str | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    """Tracked flow payloads oldest-first with their recorded ``timestamp_ms``."""
    events = best_effort_iter_events(
        event_store=event_store,
        where=f"business_flows.{event_type}",
        tenant_id=str(tenant_id),
        event_types=(str(event_type),),
        start_ms=0,
        end_ms=None,
        user_id=user_id,
    )
    is_sales_migration = event_type == "sales_pipeline@v1" and legacy_quarantine_enabled()
    migration = legacy_attribution([dict(ev["payload"]) for ev in events
                                    if isinstance(ev.get("payload"), dict)]) if is_sales_migration else {}
    wanted = str(business_id or "").strip()
    def visible(event: dict[str, Any]) -> bool:
        if str(event.get("event_type") or event.get("type")) != event_type:
            return False
        if business_id is None:
            return True
        fact = event.get("payload")
        if not wanted or not isinstance(fact, dict):
            return False
        owning = str(fact.get("business_id") or "").strip()
        if owning:
            return owning == wanted
        return bool(is_sales_migration and migration.get(str(fact.get("lead_id") or "")) == wanted)

    rows = [ev for ev in events if visible(ev)]
    rows.sort(key=lambda ev: int(ev.get("timestamp_ms") or 0))
    return [(int(ev.get("timestamp_ms") or 0), dict(ev["payload"])) for ev in rows if isinstance(ev.get("payload"), dict)]


def flow_payloads(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    user_id: str | None = None,
    business_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return tracked flow payloads oldest-first (tenant-wide when user_id is None)."""
    return [p for _, p in flow_rows(event_store, tenant_id=tenant_id, event_type=event_type, user_id=user_id, business_id=business_id)]


def stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


__all__ = ["CANON_BUSINESS_FLOW_PROJECTION", "flow_payloads", "stable_id"]
