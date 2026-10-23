from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_business_ops_summary

NOW = 1_800_000_000_000
LATER = NOW + 30 * 86_400_000


def _screen(flow, data, now=LATER):
    flow.run(partial(handle_business_ops_summary, now_ms=now), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return msg["text"], cbs


def test_attendance_buttons_write_one_fact_and_leave_the_list(flow) -> None:
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg="2027-01-20 15:00 60 Разбор")
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="cust-000042")
    assert "cpm:ev-conduct" in _screen(flow, "cpm:events")[1]
    assert "Все прошедшие" in _screen(flow, "cpm:ev-conduct", now=NOW)[0]  # not yet happened
    text, cbs = _screen(flow, "cpm:ev-conduct")
    assert "…0042" in text and cbs[0].endswith(":a") and cbs[1].endswith(":n")
    assert all(len(c.encode()) <= 64 for c in cbs)
    text, _ = _screen(flow, cbs[1])
    assert "✅ Отмечено" in text and "не пришёл" in text and "Все прошедшие встречи отмечены" in text
    assert "уже отмечено" in _screen(flow, cbs[0])[0]
    assert "Посещаемость: 0 из 1" in _screen(flow, "cpm:growth-report")[0]


def test_bad_attendance_buttons_are_refused_and_texts_preview_renders(flow) -> None:
    assert "Не получилось" in _screen(flow, "cpm:ev-att:slot_nope:a")[0]
    assert "Не получилось" in _screen(flow, "cpm:ev-att:slot_nope:x")[0]
    assert "Тексты прогрева" in _screen(flow, "cpm:ev-texts")[0]
