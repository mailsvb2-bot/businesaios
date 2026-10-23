from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import bookings as bk
from runtime.handler_impl.domains.business_flow_ops import handle_bookings

NOW = 1_800_000_000_000  # 2027-01-15 08:00 UTC
H = 3_600_000


def test_owner_opens_slot_participant_books_conflict_and_cancel(flow) -> None:
    run = partial(flow.run, partial(handle_bookings, now_ms=NOW))
    _, text = run(op="add_slot", arg="2027-01-20 15:00 90 Разбор бизнеса")
    assert "Слот открыт" in text and "15:00 МСК" in text and "90 мин" in text
    _, text = run(op="list")
    assert "1. 20.01 15:00 МСК · Разбор бизнеса" in text
    out, text = run(op="book", arg="1")
    assert out["ok"] and "Вы записаны" in text
    booked = flow.store.events[-1]["payload"]
    assert booked["customer_id"] == "u1" and len(booked["reminders_at_ms"]) == 2
    _, text = run(op="book", arg="1")
    assert "Пока пусто" not in text and "Не получилось" in text
    _, text = run(op="mine")
    assert "Разбор бизнеса" in text
    _, text = run(op="cancel", arg="1")
    assert "Запись отменена" in text
    assert "1. 20.01" in run(op="list")[1]


def test_other_user_cannot_cancel_foreign_booking(flow) -> None:
    run = partial(flow.run, partial(handle_bookings, now_ms=NOW))
    run(op="add_slot", arg="2027-01-20 15:00 Консультация")
    run(op="book", arg="1")
    out = handle_bookings(
        {"tenant_id": "t1", "user_id": "u2", "op": "cancel", "arg": "1"},
        flow.effects,
        type("E", (), {"decision": type("D", (), {"decision_id": "d", "correlation_id": "c"})})(),
        event_store=flow.store,
        now_ms=NOW,
    )
    assert out["ok"] and "Не получилось" in flow.effects.sent[-1]["text"]


def test_pull_reminder_delivered_once_when_due(flow) -> None:
    partial(flow.run, partial(handle_bookings, now_ms=NOW))(op="add_slot", arg="2027-01-16 12:00 Встреча")
    partial(flow.run, partial(handle_bookings, now_ms=NOW))(op="book", arg="1")
    start = flow.store.events[0]["payload"]["starts_at_ms"]
    later = partial(flow.run, partial(handle_bookings, now_ms=start - 23 * H))
    assert "Напоминание (за 24 часа)" in later(op="mine")[1]
    assert "Напоминание" not in later(op="mine")[1]
    assert "Напоминание (за 1 час)" in partial(flow.run, partial(handle_bookings, now_ms=start - H // 2))(op="mine")[1]


@pytest.mark.parametrize("arg", ["", "2027-13-01 10:00 X", "2020-01-01 10:00 Прошлое", "2027-01-20 10:00 1000 Долго"])
def test_invalid_slots_rejected(arg) -> None:
    with pytest.raises(ValueError):
        bk.parse_slot(arg, now_ms=NOW)
