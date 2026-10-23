from __future__ import annotations

from functools import partial

from application.business_flows import bookings as bk
from application.business_flows import event_notifications as en
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000
H = 3_600_000


def _run(flow, now, **kw):
    return partial(flow.run, partial(handle_bookings, now_ms=now))(**kw)


def test_sessions_render_day_n_of_m_and_reminders(flow) -> None:
    _, text = _run(flow, NOW, op="add_sessions", arg="2027-01-20 19:00 60 3 Марафон")
    assert "Сессии открыты (3)" in text and "день 3/3" in text
    slots = bk.replay([e["payload"] for e in flow.store.events])
    assert sorted(s.position for s in slots.values()) == [1, 2, 3]
    _run(flow, NOW, op="book", arg="2")
    s2 = next(s for s in bk.replay([e["payload"] for e in flow.store.events]).values() if s.position == 2)
    body = en.reminder_text(s2, 24 * 60)
    assert "День 2 из 3" in body and "Скоро: Марафон" in body
    assert "через 15 минут" in en.reminder_text(s2, 15)


def test_reschedule_voids_unsent_and_rematerializes(flow) -> None:
    _run(flow, NOW, op="add_slot", arg="2027-01-16 12:00 Встреча")
    _run(flow, NOW, op="book", arg="1", user_id="cust")
    start = flow.store.events[0]["payload"]["starts_at_ms"]
    assert "за 24 часа" in _run(flow, start - 23 * H, op="mine", user_id="cust")[1]
    sent_before = len(flow.effects.sent)
    _, text = _run(flow, start - 22 * H, op="reschedule_slot", arg="1 2027-01-18 12:00")
    assert "Перенесено" in text and "ревизия 1" in text
    notice = flow.effects.sent[sent_before]
    assert notice["user_id"] == "cust" and "Время изменено" in notice["text"]
    slot = bk.replay([e["payload"] for e in flow.store.events])[flow.store.events[0]["payload"]["slot_id"]]
    assert slot.revision == 1 and slot.status == "booked" and slot.customer_id == "cust"
    new_start = slot.starts_at_ms
    assert "Напоминание" not in _run(flow, start - 21 * H, op="mine", user_id="cust")[1]
    assert "за 24 часа" in _run(flow, new_start - 23 * H, op="mine", user_id="cust")[1]


def test_edit_and_bad_input(flow) -> None:
    _run(flow, NOW, op="add_slot", arg="2027-01-16 12:00 Встреча")
    assert "90 мин" in _run(flow, NOW, op="edit_slot", arg="1 90 Новая встреча")[1]
    assert "Новая встреча" in _run(flow, NOW, op="schedule")[1]
    assert "Не получилось" in _run(flow, NOW, op="edit_slot", arg="9 Х")[1]
    assert "Не получилось" in _run(flow, NOW, op="reschedule_slot", arg="1 2020-01-01 10:00")[1]
    assert "Не получилось" in _run(flow, NOW, op="add_sessions", arg="2027-01-20 19:00 60 1 X")[1]


def test_late_booking_sends_only_closest_reminder() -> None:
    s = bk.Slot("s", "T", NOW + 2 * H, 60, status="booked", customer_id="c")
    due = bk.due_reminders({"s": s}, now_ms=NOW, sent=set())
    assert [d[1] for d in due] == [180]
    assert bk.due_reminders({"s": s}, now_ms=NOW, sent={("s", 180, 0)}) == []
