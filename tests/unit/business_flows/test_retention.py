from __future__ import annotations

from functools import partial

from application.business_flows import retention as rt
from application.business_flows.bookings import Slot
from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_sales_pipeline

NOW = 1_800_000_000_000
DAY = 86_400_000


def test_cohorts_exclude_recent_and_future_customers() -> None:
    old = NOW - 60 * DAY
    slots = {
        "a": Slot("a", "x", old, 60, "booked", "anna"),
        "b": Slot("b", "x", old - DAY, 60, "booked", "anna"),
        "c": Slot("c", "x", old, 60, "booked", "boris"),
        "d": Slot("d", "x", NOW - 5 * DAY, 60, "booked", "vera"),
        "e": Slot("e", "x", old, 60, "booked", "gleb"),
        "f": Slot("f", "x", NOW + DAY, 60, "booked", "gleb"),
    }
    got = rt.candidates(slots, now_ms=NOW)
    assert [(c.customer_id, c.cohort) for c in got] == [("anna", "repeat"), ("boris", "winback")]


def test_reactivate_creates_lead_once_and_never_sends(flow) -> None:
    then = NOW - 60 * DAY
    book = partial(flow.run, partial(handle_bookings, now_ms=then - DAY))
    book(op="add_slot", arg="2026-11-16 15:00 60 Разбор")
    book(op="book", arg="1", user_id="anna")
    sales = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    out, text = sales(op="retention")
    assert "1. anna" in text and "был один раз" in text
    n = len(flow.store.events)
    _, text = sales(op="reactivate", arg="1")
    assert "Лид на возврат" in text
    assert flow.store.events[-1]["payload"]["source"] == "reactivation:winback"
    assert "уже есть" in sales(op="reactivate", arg="1")[1]
    assert len(flow.store.events) == n + 1
    assert "лид создан" in sales(op="retention")[1]
