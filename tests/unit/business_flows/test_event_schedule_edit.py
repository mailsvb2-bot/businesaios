"""Owner series schedule edit (donor _event_edit_message / _event_edit_result)."""

from __future__ import annotations

from functools import partial

from application.business_flows import bookings as bk
from application.business_flows import event_schedule_edit as ese
from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000


def _run(flow, **kw):
    return partial(flow.run, partial(handle_bookings, now_ms=NOW))(**kw)


def _slots(flow):
    return sorted(bk.replay([e["payload"] for e in flow.store.events]).values(), key=lambda s: s.position)


def test_route_is_owner_only():
    assert BUSINESS_FLOW_COMMANDS["/event_schedule"] == ("bookings@v1", "event_schedule", True)


def test_parse_window_and_message():
    at, minutes = ese.parse_window("21.01.2027 10:00-11:30", tz="Europe/Moscow")
    assert minutes == 90 and at > NOW
    for bad in ("21.01.2027 10:00", "32.01.2027 10:00-11:00", "21.01.2027 11:00-10:00"):
        try:
            ese.parse_window(bad, tz="Europe/Moscow")
        except ValueError:
            continue
        raise AssertionError(bad)
    s = [bk.Slot("a", "T", at, 60, series_id="x", position=1, session_count=2),
         bk.Slot("b", "T", at + 86_400_000, 60, series_id="x", position=2, session_count=2)]  # fmt: skip
    text = ese.edit_message(s)
    assert "Эфиров: 2" in text and "2 строки" in text and "21.01.2027 10:00-11:00" in text
    assert ese.edit_message([]) == "Это событие больше недоступно."


def test_series_edit_end_to_end(flow):
    _run(flow, op="add_sessions", arg="2027-01-20 19:00 60 3 Марафон")
    _run(flow, op="book", arg="2", user_id="cust")
    assert "Эфиров: 3" in _run(flow, op="event_schedule", arg="1")[1]
    before = len(flow.store.events)
    text = _run(flow, op="event_schedule", arg="1 20.01.2027 19:00-20:00\n21.01.2027 19:00-20:00")[1]
    assert "Нужно 3 строки" in text and len(flow.store.events) == before
    text = _run(
        flow, op="event_schedule", arg="1 20.01.2027 19:00-20:30\n20.01.2027 20:00-21:00\n22.01.2027 19:00-20:00"
    )[1]
    assert "Ничего не изменено" in text and len(flow.store.events) == before  # overlap
    sent = len(flow.effects.sent)
    text = _run(
        flow, op="event_schedule", arg="1\n20.01.2027 19:00-20:30\n23.01.2027 18:00-19:00\n24.01.2027 19:00-20:00"
    )[1]
    assert "Расписание обновлено" in text
    s1, s2, s3 = _slots(flow)
    assert s1.duration_min == 90 and s1.revision == 0
    assert s2.revision == 1 and s2.status == "booked" and s2.customer_id == "cust" and s3.revision == 1
    notices = flow.effects.sent[sent:]
    assert any(n.get("user_id") == "cust" and "Время изменено" in n["text"] for n in notices)
    assert (
        "не изменилось"
        in _run(
            flow, op="event_schedule", arg="1\n20.01.2027 19:00-20:30\n23.01.2027 18:00-19:00\n24.01.2027 19:00-20:00"
        )[1]
    )
