from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from contracts.event_store import EventStoreReader, iter_events_strict

from .contracts import SalesFunnelCountsV1, SalesFunnelSnapshotV1, SalesFunnelSourceV1
from .sales_journey import (
    SalesJourneyEvent,
    SalesJourneyState,
    reduce_sales_journey,
    sales_journey_rank,
)


@dataclass(frozen=True, slots=True)
class SalesFunnelEventMap:
    discovered: frozenset[str] = frozenset(
        {"lead_created@v1", "sales_lead_discovered", "sales_opportunity_discovered"}
    )
    inbound: frozenset[str] = frozenset(
        {"sales_inbound_received", "sales_reply_received"}
    )
    contacted: frozenset[str] = frozenset({"sales_contact_recorded"})
    need_known: frozenset[str] = frozenset({"sales_need_captured"})
    qualified: frozenset[str] = frozenset(
        {"sales_qualified", "sales_qualification_passed"}
    )
    qualification_failed: frozenset[str] = frozenset({"sales_qualification_failed"})
    offer_presented: frozenset[str] = frozenset({"sales_offer_presented"})
    checkout: frozenset[str] = frozenset(
        {"sales_checkout_started", "payment_started"}
    )
    won: frozenset[str] = frozenset(
        {
            "purchase_completed@v1",
            "sales_won",
            "payment_success",
            "payment_succeeded",
        }
    )
    lost: frozenset[str] = frozenset({"sales_lost", "sales_declined"})


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "").strip()


def _subject(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return str(
        payload.get("subject_id")
        or payload.get("customer_id")
        or payload.get("lead_id")
        or event.get("user_id")
        or ""
    ).strip()


def _source(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return str(
        payload.get("source")
        or payload.get("utm_source")
        or event.get("source")
        or "unknown"
    ).strip()[:100] or "unknown"


def _signal_for(event_type: str, mapping: SalesFunnelEventMap) -> SalesJourneyEvent | None:
    checks = (
        (mapping.inbound, SalesJourneyEvent.INBOUND_RECEIVED),
        (mapping.contacted, SalesJourneyEvent.CONTACT_RECORDED),
        (mapping.need_known, SalesJourneyEvent.NEED_CAPTURED),
        (mapping.qualified, SalesJourneyEvent.QUALIFICATION_PASSED),
        (mapping.qualification_failed, SalesJourneyEvent.QUALIFICATION_FAILED),
        (mapping.offer_presented, SalesJourneyEvent.OFFER_PRESENTED),
        (mapping.checkout, SalesJourneyEvent.CHECKOUT_STARTED),
        (mapping.won, SalesJourneyEvent.PAYMENT_CONFIRMED),
        (mapping.lost, SalesJourneyEvent.DECLINED),
    )
    for event_types, signal in checks:
        if event_type in event_types:
            return signal
    return None


def _counts(states: dict[str, SalesJourneyState]) -> SalesFunnelCountsV1:
    engaged = qualified = checkout = won = lost = 0
    for state in states.values():
        if state == SalesJourneyState.LOST:
            lost += 1
            continue
        rank = sales_journey_rank(state)
        engaged += rank >= sales_journey_rank(SalesJourneyState.ENGAGED)
        qualified += rank >= sales_journey_rank(SalesJourneyState.QUALIFIED)
        checkout += rank >= sales_journey_rank(SalesJourneyState.CHECKOUT)
        won += state == SalesJourneyState.WON
    return SalesFunnelCountsV1(
        discovered=len(states),
        engaged=int(engaged),
        qualified=int(qualified),
        checkout=int(checkout),
        won=int(won),
        lost=int(lost),
    )


def empty_sales_funnel(*, tenant_id: str, start_ms: int, end_ms: int) -> SalesFunnelSnapshotV1:
    return SalesFunnelSnapshotV1(
        tenant_id=str(tenant_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
    )


def read_sales_funnel(
    store: EventStoreReader,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_map: SalesFunnelEventMap | None = None,
) -> SalesFunnelSnapshotV1:
    """Project hard tenant-scoped funnel evidence from the canonical EventStore."""

    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    start = int(start_ms)
    end = int(end_ms)
    if end <= start:
        raise ValueError("end_ms must be greater than start_ms")
    mapping = event_map or SalesFunnelEventMap()
    states: dict[str, SalesJourneyState] = {}
    sources: dict[str, str] = {}

    for event in iter_events_strict(store, tenant_id=tenant, start_ms=start, end_ms=end):
        row = dict(event or {})
        event_type = _event_type(row)
        is_discovery = event_type in mapping.discovered
        signal = _signal_for(event_type, mapping)
        if not is_discovery and signal is None:
            continue
        subject = _subject(row)
        if not subject:
            continue
        source = _source(row)
        if subject not in states:
            states[subject] = SalesJourneyState.DISCOVERED
            sources[subject] = source
        elif sources.get(subject, "unknown") == "unknown" and source != "unknown":
            sources[subject] = source
        if signal is not None:
            states[subject] = reduce_sales_journey(states[subject], signal).current

    by_source_states: dict[str, dict[str, SalesJourneyState]] = defaultdict(dict)
    for subject, state in states.items():
        by_source_states[sources.get(subject, "unknown")][subject] = state

    return SalesFunnelSnapshotV1(
        tenant_id=tenant,
        start_ms=start,
        end_ms=end,
        total=_counts(states),
        by_source=tuple(
            SalesFunnelSourceV1(source=source, counts=_counts(rows))
            for source, rows in sorted(by_source_states.items())
        ),
    )


__all__ = [
    "SalesFunnelEventMap",
    "empty_sales_funnel",
    "read_sales_funnel",
]
