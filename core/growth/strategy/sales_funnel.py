from __future__ import annotations

from collections import defaultdict
from typing import Any

from contracts.event_store import EventStoreReader, iter_events_strict

_STAGES = ("discovered", "engaged", "need_known", "qualified", "offer_presented", "checkout", "won")
_EVENTS: dict[str, tuple[int, str | None]] = {
    "lead_created@v1": (0, None), "sales_lead_discovered": (0, None), "sales_opportunity_discovered": (0, None),
    "sales_inbound_received": (1, "open"), "sales_reply_received": (1, "open"), "sales_contact_recorded": (1, "open"),
    "sales_need_captured": (2, "open"), "sales_qualified": (3, "open"), "sales_qualification_passed": (3, "open"),
    "sales_offer_presented": (4, "open"), "sales_checkout_started": (5, "open"), "payment_started": (5, "open"),
    "purchase_completed@v1": (6, "won"), "sales_won": (6, "won"), "payment_success": (6, "won"), "payment_succeeded": (6, "won"),
    "sales_lost": (-1, "lost"), "sales_declined": (-1, "lost"), "sales_qualification_failed": (-1, "lost"),
}


def reduce_sales_evidence(stage: str, disposition: str, event_type: str) -> tuple[str, str]:
    """Replay-safe evidence reducer; handoff is intentionally not a funnel stage."""
    if disposition == "won" or event_type not in _EVENTS:
        return stage, disposition
    rank, next_disposition = _EVENTS[event_type]
    if rank < 0:
        return stage, "lost"
    current = _STAGES.index(stage) if stage in _STAGES else 0
    next_stage = _STAGES[max(current, rank)]
    return next_stage, next_disposition or disposition


def _subject(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return str(payload.get("subject_id") or payload.get("customer_id") or payload.get("lead_id") or row.get("user_id") or "").strip()


def _source(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return str(payload.get("source") or payload.get("utm_source") or row.get("source") or "unknown").strip()[:100] or "unknown"


def _counts(states: dict[str, tuple[str, str]]) -> dict[str, int | float]:
    ranks = [_STAGES.index(stage) for stage, _disposition in states.values()]
    discovered, engaged, qualified, checkout = len(states), sum(r >= 1 for r in ranks), sum(r >= 3 for r in ranks), sum(r >= 5 for r in ranks)
    won = sum(disposition == "won" for _stage, disposition in states.values())
    lost = sum(disposition == "lost" for _stage, disposition in states.values())
    pct = lambda n, d: 0.0 if not d else round(n / d * 100.0, 1)
    return {"discovered": discovered, "engaged": engaged, "qualified": qualified, "checkout": checkout, "won": won, "lost": lost,
            "engagement_percent": pct(engaged, discovered), "qualification_percent": pct(qualified, engaged),
            "checkout_percent": pct(checkout, qualified), "win_percent": pct(won, discovered)}


def empty_sales_funnel(*, tenant_id: str, start_ms: int, end_ms: int) -> dict[str, Any]:
    return {"schema_version": 1, "tenant_id": str(tenant_id), "start_ms": int(start_ms), "end_ms": int(end_ms), "total": _counts({}), "by_source": []}


def read_sales_funnel(store: EventStoreReader, *, tenant_id: str, start_ms: int, end_ms: int) -> dict[str, Any]:
    """Project tenant-scoped hard sales evidence from the canonical EventStore."""
    tenant, start, end = str(tenant_id or "").strip(), int(start_ms), int(end_ms)
    if not tenant:
        raise ValueError("tenant_id is required")
    if end <= start:
        raise ValueError("end_ms must be greater than start_ms")
    states: dict[str, tuple[str, str]] = {}
    sources: dict[str, str] = {}
    for event in iter_events_strict(store, tenant_id=tenant, start_ms=start, end_ms=end):
        row, event_type = dict(event or {}), str((event or {}).get("event_type") or "").strip()
        if event_type not in _EVENTS:
            continue
        subject = _subject(row)
        if not subject:
            continue
        source = _source(row)
        states.setdefault(subject, ("discovered", "open"))
        sources.setdefault(subject, source)
        if sources[subject] == "unknown" and source != "unknown":
            sources[subject] = source
        states[subject] = reduce_sales_evidence(*states[subject], event_type)
    grouped: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for subject, state in states.items():
        grouped[sources.get(subject, "unknown")][subject] = state
    return {"schema_version": 1, "tenant_id": tenant, "start_ms": start, "end_ms": end, "total": _counts(states),
            "by_source": [{"source": source, "counts": _counts(rows)} for source, rows in sorted(grouped.items())]}


__all__ = ["empty_sales_funnel", "read_sales_funnel", "reduce_sales_evidence"]
