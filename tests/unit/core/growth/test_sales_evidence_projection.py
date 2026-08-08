from __future__ import annotations

import time

from core.growth.strategy.sales_funnel import read_sales_funnel, reduce_sales_evidence
from core.growth.strategy.signals import build_signals
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _append(store, tenant, ts, user, kind, payload=None):
    store.append_event({"tenant_id": tenant, "timestamp_ms": ts, "user_id": user, "event_type": kind, "payload": payload or {}})


def test_reducer_preserves_stage_reopens_loss_and_keeps_win_terminal() -> None:
    state = ("discovered", "open")
    for kind in ("sales_qualified", "sales_declined"):
        state = reduce_sales_evidence(*state, kind)
    assert state == ("qualified", "lost")
    assert reduce_sales_evidence(*state, "sales_inbound_received") == ("qualified", "open")
    won = reduce_sales_evidence("qualified", "open", "purchase_completed@v1")
    assert won == ("won", "won")
    assert reduce_sales_evidence(*won, "sales_declined") == won
    assert reduce_sales_evidence(*state, "sales_human_requested") == state


def test_funnel_and_growth_signal_share_tenant_scoped_canonical_evidence() -> None:
    store, now = MemoryEventStore(), int(time.time() * 1000)
    rows = (
        ("tenant-a", now - 6000, "lead-1", "lead_created@v1", {"source": "telegram"}),
        ("tenant-a", now - 5000, "lead-1", "sales_qualified", {"source": "telegram"}),
        ("tenant-a", now - 4000, "lead-1", "sales_declined", {"source": "telegram"}),
        ("tenant-a", now - 3000, "lead-1", "sales_checkout_started", {"source": "telegram"}),
        ("tenant-a", now - 2000, "lead-1", "purchase_completed@v1", {"source": "telegram"}),
        ("tenant-a", now - 1500, "operator", "sales_lead_discovered", {"subject_id": "lead-2", "source": "website"}),
        ("tenant-a", now - 1000, "operator", "sales_qualification_failed", {"subject_id": "lead-2", "source": "website"}),
        ("tenant-b", now - 500, "other", "purchase_completed@v1", {"source": "telegram"}),
    )
    for row in rows:
        _append(store, *row)

    snapshot = read_sales_funnel(store, tenant_id="tenant-a", start_ms=now - 10_000, end_ms=now)
    assert snapshot["total"] == {
        "discovered": 2, "engaged": 1, "qualified": 1, "checkout": 1, "won": 1, "lost": 1,
        "engagement_percent": 50.0, "qualification_percent": 100.0,
        "checkout_percent": 100.0, "win_percent": 50.0,
    }
    assert {item["source"] for item in snapshot["by_source"]} == {"telegram", "website"}
    signals = build_signals(store, tenant_id="tenant-a")
    assert signals.sales_funnel["tenant_id"] == "tenant-a"
    assert signals.sales_funnel["total"]["won"] == 1
