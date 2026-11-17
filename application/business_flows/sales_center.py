"""Sales Center: one normalized, read-only view over the sales sources a business really has.

Pure. Sources are the canonical channel pipeline (sales_pipeline@v1 facts from
Telegram/VK/MAX inbound) and every CRM whose contacts *and* deals were confirmed
by a live read. Nothing is written; unknown values stay ``None`` (never zero).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_SALES_CENTER_VIEW = True


def _live_ok(row: Mapping[str, Any]) -> bool:
    return (str(row.get("mode") or "").lower() == "live" and row.get("accepted") is True
            and str(row.get("status") or "").lower() == "live_executed")


def latest_read(history: list[Mapping[str, Any]], operation: str) -> Mapping[str, Any] | None:
    ok = [r for r in history if isinstance(r, Mapping) and _live_ok(r) and str(r.get("operation") or "") == operation]
    return max(ok, key=lambda r: str(r.get("recorded_at_utc") or ""), default=None)


def resource_count(row: Mapping[str, Any] | None) -> int | None:
    if not row:
        return None
    for part in ("parsed_response", "transport_response"):
        value = (row.get(part) or {}).get("resource_count") if isinstance(row.get(part), Mapping) else None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def channel_source(*, leads: Mapping[str, Any], last_fact_ms: int | None, connected_channels: list[str]) -> dict[str, Any]:
    contacts = {(getattr(x, "source", ""), getattr(x, "customer_id", "")) for x in leads.values() if getattr(x, "customer_id", "")}
    return {
        "key": "channels", "kind": "channels", "title": "Обращения из мессенджеров",
        "providers": list(connected_channels), "connected": bool(connected_channels or leads),
        "read_confirmed": bool(leads), "contacts": len(contacts) if leads else None,
        "deals": len(leads) if leads else None, "last_read_ms": last_fact_ms, "last_read_at": None,
    }


def crm_source(*, provider: Mapping[str, Any], history: list[Mapping[str, Any]]) -> dict[str, Any]:
    contacts, deals = latest_read(history, "contact_sync"), latest_read(history, "deal_sync")
    stamps = [str(r.get("recorded_at_utc") or "") for r in (contacts, deals) if r]
    return {
        "key": str(provider.get("provider_key") or ""), "kind": "crm",
        "title": str(provider.get("title") or provider.get("provider_key") or ""),
        "providers": [str(provider.get("provider_key") or "")], "connected": bool(provider.get("connected")),
        "read_confirmed": bool(contacts and deals), "contacts": resource_count(contacts),
        "deals": resource_count(deals), "last_read_ms": None, "last_read_at": min(stamps) if len(stamps) == 2 else None,
    }


def choose(sources: list[dict[str, Any]], requested: str = "") -> dict[str, Any]:
    """Canonical source: a connected CRM with confirmed contact+deal reads (system of record for
    deals), else the channel pipeline when it has leads. The owner may view another *available*
    source; an unavailable request falls back to the canonical one."""
    available = [s for s in sources if s["connected"] and s["read_confirmed"]]
    canonical = next((s for s in available if s["kind"] == "crm"), None) or next(iter(available), None)
    chosen = next((s for s in available if s["key"] == requested), canonical)
    return {
        "sources": sources, "available": [s["key"] for s in available],
        "canonical_source": canonical["key"] if canonical else None,
        "selected_source": chosen["key"] if chosen else None,
        "selection_rule": "crm_with_confirmed_contact_and_deal_reads_then_channel_pipeline",
        "write_actions_enabled": False,
    }


__all__ = ["CANON_SALES_CENTER_VIEW", "channel_source", "choose", "crm_source", "latest_read", "resource_count"]
