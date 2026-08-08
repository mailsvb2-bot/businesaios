from __future__ import annotations

import time

from core.growth.strategy.sales_funnel import read_sales_funnel, reduce_sales_evidence
from core.growth.strategy.signals import build_signals
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_sales_evidence_replay_preserves_progress_and_terminal_win() -> None:
    state = reduce_sales_evidence("discovered", "open", "sales_qualified")
    assert reduce_sales_evidence(*state, "sales_declined") == ("qualified", "lost")
    assert reduce_sales_evidence("qualified", "lost", "sales_inbound_received") == ("qualified", "open")
    won = reduce_sales_evidence("qualified", "open", "purchase_completed@v1")
    assert won == ("won", "won")
    assert reduce_sales_evidence(*won, "sales_declined") == won


def test_funnel_is_tenant_subject_scoped_and_wired_into_growth() -> None:
    store, now = MemoryEventStore(), int(time.time() * 1000)
    rows = (
        ("tenant-a", "lead-1", "lead_created@v1", {"source": "telegram"}),
        ("tenant-a", "lead-1", "purchase_completed@v1", {"source": "telegram"}),
        ("tenant-a", "operator", "sales_lead_discovered", {"subject_id": "lead-2", "source": "website"}),
        ("tenant-a", "operator", "sales_qualification_failed", {"subject_id": "lead-2", "source": "website"}),
        ("tenant-b", "other", "purchase_completed@v1", {"source": "telegram"}),
    )
    for index, (tenant, user, kind, payload) in enumerate(rows):
        store.append_event({"tenant_id": tenant, "timestamp_ms": now - 5000 + index, "user_id": user, "event_type": kind, "payload": payload})
    snapshot = read_sales_funnel(store, tenant_id="tenant-a", start_ms=now - 10_000, end_ms=now)
    assert snapshot["total"]["discovered"] == 2 and snapshot["total"]["won"] == 1 and snapshot["total"]["lost"] == 1
    assert {item["source"] for item in snapshot["by_source"]} == {"telegram", "website"}
    assert build_signals(store, tenant_id="tenant-a").sales_funnel["total"]["won"] == 1
