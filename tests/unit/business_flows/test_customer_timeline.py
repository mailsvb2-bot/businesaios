from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import customer_timeline as ct
from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_business_ops_summary

NOW = 1_800_000_000_000
LATER = NOW + 30 * 86_400_000


def _screen(flow, data, now=LATER):
    flow.run(partial(handle_business_ops_summary, now_ms=now), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    return msg["text"], [b["callback_data"] for r in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in r]


def test_history_screen_lists_booking_and_attendance_in_order(flow) -> None:
    run = partial(handle_bookings, now_ms=NOW)
    flow.run(run, op="add_slot", arg="2027-01-20 15:00 60 Разбор")
    flow.run(run, op="add_slot", arg="2027-01-22 15:00 60 Сессия")
    flow.run(run, op="book", arg="1", user_id="cust-000042")
    _, cbs = _screen(flow, "cpm:customer:cust-000042")
    assert "cpm:cust-time:cust-000042" in cbs
    text, _ = _screen(flow, "cpm:cust-time:cust-000042")
    assert "• 20.01.2027 · Запись — Разбор" in text and "Посещение — не отмечено" in text
    assert "неактуальна" in _screen(flow, "cpm:cust-time:nobody")[0]


def test_format_lines_shows_tail_with_hidden_notice() -> None:
    es = [ct.Entry(NOW + i * 86_400_000, "booking", "Запись", str(i)) for i in range(10)]
    lines = ct.format_lines(es, max_entries=3)
    assert lines[0] == "• Показаны последние 3 из 10 событий" and lines[-1].endswith("— 9")
    with pytest.raises(ValueError):
        ct.format_lines(es, max_entries=0)
    with pytest.raises(ValueError):
        ct.Entry(-1, "x", "y")
