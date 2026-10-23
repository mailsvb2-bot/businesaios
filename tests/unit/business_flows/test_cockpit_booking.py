from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary

NOW = 1_800_000_000_000  # 2027-01-15 МСК


def _screen(flow, data):
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return msg["text"], cbs


def test_picker_walks_month_date_time_duration_and_writes_add_slot_fact(flow) -> None:
    text, cbs = _screen(flow, "cpm:bookings:0")
    assert "cpm:bk-open" in cbs
    text, cbs = _screen(flow, "cpm:bk-open")
    assert cbs[0] == "cpm:bk-months:0"
    text, cbs = _screen(flow, "cpm:bk-months:0")
    assert cbs[0] == "cpm:bk-dates:0:202701" and "cpm:bk-months:0:1" in cbs
    text, cbs = _screen(flow, "cpm:bk-dates:0:202701")
    assert cbs[0] == "cpm:bk-times:0:20270115"  # past days hidden
    text, cbs = _screen(flow, "cpm:bk-times:0:20270120")
    assert cbs[0] == "cpm:bk-dur:0:202701200800" and "cpm:bk-times:0:20270120p1" in cbs
    text, cbs = _screen(flow, "cpm:bk-dur:0:202701201030")
    assert "cpm:bk-new:0-202701201030:60" in cbs
    assert all(len(c.encode()) <= 64 for c in cbs)
    text, cbs = _screen(flow, "cpm:bk-new:0-202701201030:60")
    assert "✅ Свободное время добавлено: 20.01 10:30 МСК · Встреча (60 мин)" in text
    assert "20.01 10:30" in _screen(flow, "cpm:bookings:0")[0]
    assert "уже добавлено" in _screen(flow, "cpm:bk-new:0-202701201030:60")[0]


def test_stale_and_out_of_window_selections_are_refused(flow) -> None:
    assert "неактуальна" in _screen(flow, "cpm:bk-dates:0:202612")[0]
    assert "неактуальна" in _screen(flow, "cpm:bk-months:5")[0]
    assert "неактуальна" in _screen(flow, "cpm:bk-dur:0:202701201031")[0]
    assert "Не получилось" in _screen(flow, "cpm:bk-new:0-202801201030:60")[0]
    assert "Не получилось" in _screen(flow, "cpm:bk-new:0-202701201030:45")[0]
