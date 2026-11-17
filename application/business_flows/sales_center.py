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


# --- Funnel (P1-19): one normalized stage ladder over every source ------------
STAGES = ("discovered", "engaged", "need_known", "qualified", "offer_presented", "checkout", "won")
STALE_AFTER_MS = 14 * 86_400_000
# Per-provider stage read model: provider stage key -> normalized stage (or "lost").
STAGE_MAPS: dict[str, dict[str, str]] = {
    "channels": {**{s: s for s in STAGES}, "lost": "lost"},
    "hubspot": {  # HubSpot default sales pipeline stage ids
        "appointmentscheduled": "engaged", "qualifiedtobuy": "qualified", "presentationscheduled": "offer_presented",
        "decisionmakerboughtin": "offer_presented", "contractsent": "checkout",
        "closedwon": "won", "closedlost": "lost",
    },
}


def normalize_stage(provider_key: str, stage_key: object) -> str | None:
    return STAGE_MAPS.get(provider_key, {}).get(str(stage_key or "").strip().lower())


def _funnel(reached: dict[str, int], *, won: int, lost: int, stale: int, open_: int, unmapped: int, basis: str) -> dict[str, Any]:
    conv = []
    for prev, cur in zip(STAGES, STAGES[1:]):
        base = reached.get(prev, 0)
        conv.append({"from": prev, "to": cur, "reached": reached.get(cur, 0), "base": base,
                     "rate": round(reached.get(cur, 0) / base, 4) if base else None})
    closed = won + lost
    return {"won": won, "lost": lost, "stale": stale, "open": open_, "unmapped": unmapped,
            "win_rate": round(won / closed, 4) if closed else None, "stage_conversion": conv,
            "reached": {s: reached.get(s, 0) for s in STAGES}, "basis": basis,
            "stale_after_days": STALE_AFTER_MS // 86_400_000}


def pipeline_funnel(rows: list[tuple[int, Mapping[str, Any]]], *, now_ms: int) -> dict[str, Any] | None:
    """Channel pipeline funnel from sales_pipeline@v1 facts: the highest stage each lead really reached."""
    rank = {s: i for i, s in enumerate(STAGES)}
    best: dict[str, int] = {}
    final: dict[str, str] = {}
    last: dict[str, int] = {}
    for ts, p in rows:
        lid, step = str(p.get("lead_id") or ""), p.get("step")
        if not lid:
            continue
        if step in ("lead_added", "lead_inbound"):
            best.setdefault(lid, rank["engaged"] if step == "lead_inbound" else 0)
            final.setdefault(lid, "open")
        if lid not in best:
            continue
        last[lid] = max(last.get(lid, 0), int(ts))
        if step == "lead_inbound":
            best[lid] = max(best[lid], rank["engaged"])
        elif step == "lead_event":
            stage = str(p.get("stage") or "")
            if stage == "lost":
                final[lid] = "lost"
            elif stage in rank:
                best[lid] = max(best[lid], rank[stage])
                final[lid] = "won" if stage == "won" else "open"
        elif step == "lead_reopened":
            final[lid] = "open"
    if not best:
        return None
    reached = {s: sum(1 for b in best.values() if b >= i) for i, s in enumerate(STAGES)}
    open_ids = [lid for lid, f in final.items() if f == "open"]
    return _funnel(reached, won=sum(f == "won" for f in final.values()), lost=sum(f == "lost" for f in final.values()),
                   stale=sum(1 for lid in open_ids if now_ms - last.get(lid, 0) > STALE_AFTER_MS),
                   open_=len(open_ids), unmapped=0, basis="highest_stage_reached")


def deal_funnel(deals: list[Any], *, provider_key: str, now_ms: int) -> dict[str, Any] | None:
    """CRM funnel from canonical Deal records (DealRegistry) through the provider stage map.

    Only the current stage is known, so a deal counts as having reached every stage up to it;
    lost deals count in «lost» but not in stage conversion; unmapped stages are reported, not guessed.
    """
    active = [d for d in deals if str(getattr(d, "lifecycle_status", "active")) == "active"]
    if not active:
        return None
    rank = {s: i for i, s in enumerate(STAGES)}
    reached = dict.fromkeys(STAGES, 0)
    won = lost = stale = open_ = unmapped = 0
    for d in active:
        stage = normalize_stage(provider_key, getattr(d, "stage_key", None))
        if stage is None:
            unmapped += 1
            continue
        if stage == "lost":
            lost += 1
            continue
        for s in STAGES[: rank[stage] + 1]:
            reached[s] += 1
        if stage == "won":
            won += 1
        else:
            open_ += 1
            stale += int(now_ms - int(getattr(d, "updated_at_ms", 0) or 0) > STALE_AFTER_MS)
    return _funnel(reached, won=won, lost=lost, stale=stale, open_=open_, unmapped=unmapped, basis="current_stage")


__all__ = ["CANON_SALES_CENTER_VIEW", "STAGE_MAPS", "deal_funnel", "normalize_stage", "pipeline_funnel", "channel_source", "choose", "crm_source", "latest_read", "resource_count"]
