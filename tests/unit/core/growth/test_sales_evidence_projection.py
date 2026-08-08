from __future__ import annotations

import time

from core.growth.strategy.sales_funnel import read_sales_funnel
from core.growth.strategy.sales_journey import (
    SalesJourneyDisposition,
    SalesJourneyEvent,
    SalesJourneyState,
    reduce_sales_journey,
    replay_sales_journey,
)
from core.growth.strategy.signals import build_signals
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _append(
    store: MemoryEventStore,
    *,
    tenant_id: str,
    timestamp_ms: int,
    user_id: str,
    event_type: str,
    payload: dict | None = None,
) -> None:
    store.append_event(
        {
            "tenant_id": tenant_id,
            "timestamp_ms": timestamp_ms,
            "user_id": user_id,
            "event_type": event_type,
            "payload": dict(payload or {}),
        }
    )


def test_sales_journey_preserves_progress_and_reopens_lost_evidence() -> None:
    qualified = reduce_sales_journey(
        SalesJourneyState.DISCOVERED,
        SalesJourneyEvent.QUALIFICATION_PASSED,
    ).current
    assert qualified.state == SalesJourneyState.QUALIFIED
    assert qualified.disposition == SalesJourneyDisposition.OPEN

    lost = reduce_sales_journey(qualified, SalesJourneyEvent.DECLINED).current
    assert lost.state == SalesJourneyState.QUALIFIED
    assert lost.disposition == SalesJourneyDisposition.LOST

    handoff = reduce_sales_journey(lost, SalesJourneyEvent.HUMAN_REQUESTED).current
    assert handoff == lost

    reopened = reduce_sales_journey(lost, SalesJourneyEvent.INBOUND_RECEIVED).current
    assert reopened.state == SalesJourneyState.QUALIFIED
    assert reopened.disposition == SalesJourneyDisposition.OPEN

    won = reduce_sales_journey(reopened, SalesJourneyEvent.PAYMENT_CONFIRMED).current
    assert won.state == SalesJourneyState.WON
    assert won.disposition == SalesJourneyDisposition.WON
    assert reduce_sales_journey(won, SalesJourneyEvent.DECLINED).current == won


def test_sales_journey_replay_is_repeat_safe() -> None:
    events = (
        SalesJourneyEvent.INBOUND_RECEIVED,
        SalesJourneyEvent.INBOUND_RECEIVED,
        SalesJourneyEvent.NEED_CAPTURED,
        SalesJourneyEvent.QUALIFICATION_PASSED,
        SalesJourneyEvent.OFFER_PRESENTED,
        SalesJourneyEvent.CHECKOUT_STARTED,
        SalesJourneyEvent.PAYMENT_CONFIRMED,
    )
    first = replay_sales_journey(events)
    second = replay_sales_journey(events)
    assert first == second
    assert first.state == SalesJourneyState.WON
    assert first.disposition == SalesJourneyDisposition.WON


def test_sales_funnel_is_tenant_scoped_subject_scoped_and_recovery_safe() -> None:
    store = MemoryEventStore()
    rows = (
        ("tenant-a", 100, "lead-1", "lead_created@v1", {"source": "telegram"}),
        ("tenant-a", 200, "lead-1", "sales_inbound_received", {"source": "telegram"}),
        ("tenant-a", 300, "lead-1", "sales_qualified", {"source": "telegram"}),
        ("tenant-a", 400, "lead-1", "sales_declined", {"source": "telegram"}),
        ("tenant-a", 500, "lead-1", "sales_checkout_started", {"source": "telegram"}),
        ("tenant-a", 600, "lead-1", "purchase_completed@v1", {"source": "telegram"}),
        (
            "tenant-a",
            700,
            "operator-7",
            "sales_lead_discovered",
            {"subject_id": "lead-2", "source": "website"},
        ),
        (
            "tenant-a",
            800,
            "operator-7",
            "sales_qualification_failed",
            {"subject_id": "lead-2", "source": "website"},
        ),
        ("tenant-b", 900, "lead-other", "purchase_completed@v1", {"source": "telegram"}),
    )
    for tenant_id, timestamp_ms, user_id, event_type, payload in rows:
        _append(
            store,
            tenant_id=tenant_id,
            timestamp_ms=timestamp_ms,
            user_id=user_id,
            event_type=event_type,
            payload=payload,
        )

    snapshot = read_sales_funnel(
        store,
        tenant_id="tenant-a",
        start_ms=0,
        end_ms=10_000,
    )

    assert snapshot.total.discovered == 2
    assert snapshot.total.engaged == 1
    assert snapshot.total.qualified == 1
    assert snapshot.total.checkout == 1
    assert snapshot.total.won == 1
    assert snapshot.total.lost == 1
    assert snapshot.total.win_percent == 50.0
    assert {item.source for item in snapshot.by_source} == {"telegram", "website"}
    website = next(item for item in snapshot.by_source if item.source == "website")
    assert website.counts.lost == 1
    assert website.counts.discovered == 1


def test_growth_signals_receive_sales_funnel_from_same_event_store() -> None:
    store = MemoryEventStore()
    now_ms = int(time.time() * 1000)
    _append(
        store,
        tenant_id="tenant-a",
        timestamp_ms=now_ms - 2_000,
        user_id="lead-1",
        event_type="lead_created@v1",
        payload={"source": "web_chat"},
    )
    _append(
        store,
        tenant_id="tenant-a",
        timestamp_ms=now_ms - 1_000,
        user_id="lead-1",
        event_type="purchase_completed@v1",
        payload={"source": "web_chat", "amount_minor": 10_000},
    )

    signals = build_signals(store, tenant_id="tenant-a")

    assert signals.sales_funnel.tenant_id == "tenant-a"
    assert signals.sales_funnel.total.discovered == 1
    assert signals.sales_funnel.total.won == 1
    assert signals.sales_funnel.total.win_percent == 100.0
