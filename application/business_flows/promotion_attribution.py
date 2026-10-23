"""Exact promotion outcome attribution (port of donor promotion_attribution).

Pure over timestamped ``bookings@v1`` / ``sales_pipeline@v1`` facts: ``(occurred_at_iso, payload)``.
No cross-campaign credit: ``won`` needs a booked promotion event for that campaign, a lead
of the same customer (same offering when both sides record one) and a ``won`` transition at or
after that booking, inside the reporting window. Source maps keep the exact public token.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from application.business_flows.customer_timeline_sources import parse_timestamp

CANON_PROMOTION_ATTRIBUTION = True
Row = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class PromotionAttribution:
    leads: dict[str, frozenset[str]]
    bookings: dict[str, frozenset[str]]
    won: dict[str, frozenset[str]]
    source_leads: dict[str, frozenset[str]] = field(default_factory=dict)
    source_bookings: dict[str, frozenset[str]] = field(default_factory=dict)
    source_won: dict[str, frozenset[str]] = field(default_factory=dict)


def event_window(date_from: str, date_to: str, *, zone: ZoneInfo) -> tuple[datetime, datetime]:
    try:
        start_d, end_d = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError as exc:
        raise ValueError("analytics dates must use YYYY-MM-DD") from exc
    if start_d > end_d:
        raise ValueError("analytics date_from must not be after date_to")
    start = datetime.combine(start_d, time.min, tzinfo=zone).astimezone(UTC)
    return start, datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)


def _freeze(d: dict[str, set[str]]) -> dict[str, frozenset[str]]:
    return {k: frozenset(v) for k, v in d.items()}


def attribute(booking_rows: Iterable[Row], sales_rows: Iterable[Row], *, campaign_ids: set[str],
              start: datetime, until: datetime) -> PromotionAttribution:
    if not campaign_ids:
        return PromotionAttribution({}, {}, {})
    tokens: dict[str, str] = {}
    offering: dict[str, str] = {}
    touches: list[tuple[datetime, str, str, str, str]] = []  # at, kind, campaign, customer, token
    for at_raw, p in booking_rows:
        step, cid = p.get("step"), str(p.get("promotion_id") or "")
        if step == "promotion_saved" and cid:
            tokens.setdefault(cid, str(p.get("source_token") or ""))
            if p.get("offering_id"):
                offering[cid] = str(p["offering_id"])
        elif step in ("promotion_opened", "booked") and cid:
            at = parse_timestamp(at_raw, field="occurred_at")
            if start <= at < until:
                tok = str(p.get("source_token") or "") or tokens.get(cid, "")
                touches.append((at, "opened" if step == "promotion_opened" else "booked", cid,
                                str(p.get("customer_id") or ""), tok))
    lead_customer: dict[str, str] = {}
    lead_offering: dict[str, str] = {}
    wins: list[tuple[datetime, str]] = []  # at, lead
    for at_raw, p in sales_rows:
        lid = str(p.get("lead_id") or "")
        if p.get("step") == "lead_inbound" and lid:
            lead_customer.setdefault(lid, str(p.get("customer_id") or ""))
            if p.get("offering_id"):
                lead_offering.setdefault(lid, str(p["offering_id"]))
        elif p.get("step") == "lead_event" and p.get("stage") == "won" and lid:
            wins.append((parse_timestamp(at_raw, field="occurred_at"), lid))
    sets: dict[str, dict[str, set[str]]] = {k: defaultdict(set) for k in ("l", "b", "w", "sl", "sb", "sw")}
    for at, kind, cid, cust, tok in touches:
        if cid not in campaign_ids:
            continue
        sets["l" if kind == "opened" else "b"][cid].add(cust)
        if kind == "booked":  # donor records an opened touch for every promoted booking
            sets["l"][cid].add(cust)
        if tok:
            sets["sl"][tok].add(cust)
            if kind == "booked":
                sets["sb"][tok].add(cust)
        if kind != "booked":
            continue
        for won_at, lid in wins:
            off_ok = not (offering.get(cid) and lead_offering.get(lid)) or offering[cid] == lead_offering[lid]
            if lead_customer.get(lid) == cust and off_ok and at <= won_at < until:
                sets["w"][cid].add(cust)
                if tok:
                    sets["sw"][tok].add(cust)
    return PromotionAttribution(*(_freeze(sets[k]) for k in ("l", "b", "w", "sl", "sb", "sw")))


__all__ = ["CANON_PROMOTION_ATTRIBUTION", "PromotionAttribution", "attribute", "event_window"]
