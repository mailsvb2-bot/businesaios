from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import growth_cockpit as gc
from runtime.handler_impl.domains.business_flow_ops import (
    handle_bookings,
    handle_business_ops_summary,
    handle_sales_pipeline,
)

NOW = 1_800_000_000_000
LATER = NOW + 30 * 86_400_000


def _screen(flow, data, now=LATER):
    flow.run(partial(handle_business_ops_summary, now_ms=now), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    return msg["text"], [b["callback_data"] for r in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in r]


def test_queue_orders_handoff_then_attendance_then_open_time(flow) -> None:
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg="2027-01-20 15:00 60 Разбор")
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="cust-000042")
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="add", arg="Анна | сайт")
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="event", arg="1 handoff")
    text, cbs = _screen(flow, "cpm:growth-now")
    assert "Главное: Подключиться: Анна" in text and "Отметить посещение" in text
    assert cbs[0].startswith("cpm:sales-lead:") and cbs[1] == "cpm:ev-conduct" and cbs[2] == "cpm:bk-open"
    assert "рекламу здесь не учитываются" in text
    assert "cpm:growth-now" in _screen(flow, "cpm:growth")[1]


def test_limit_is_validated() -> None:
    with pytest.raises(ValueError):
        gc.action_queue(object(), limit=0)
    assert gc.next_action(()).title == "Ничего срочного"
