from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import event_series as es
from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_business_admin, handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15 08:00 UTC
H, D = 3_600_000, 86_400_000


def _book(flow, slot_arg="2027-01-20 15:00 60 Разбор"):
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg=slot_arg)
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="u2")
    return next(e["payload"] for e in flow.store.events if e["payload"].get("step") == "slot_opened")


def _series(flow, now, **kw):
    return flow.run(partial(handle_event_series, now_ms=now), **kw)


def test_warmups_due_once_and_not_after_start(flow) -> None:
    slot = _book(flow)
    start = slot["starts_at_ms"]
    _series(flow, start - 3 * D + 1, op="dispatch")
    warm = [m for m in flow.effects.sent if m.get("user_id") == "u2" and "осталось" in m["text"]]
    assert len(warm) == 1 and "3 дня" in warm[0]["text"]
    _, text = _series(flow, start - 3 * D + 2, op="dispatch")
    assert "отправлено 0 из 0" in text
    _series(flow, start - D + 1, op="dispatch")
    _, text = _series(flow, start + 1, op="dispatch")
    assert "отправлено 0 из 0" in text


def test_followups_need_consent_attendance_and_offer_url(flow) -> None:
    slot = _book(flow)
    end = slot["starts_at_ms"] + 60 * 60_000
    _, text = _series(flow, end + H, op="dispatch")
    assert "offer_url" in text and "0 из 0" in text
    flow.run(handle_business_admin, op="setting", arg="offer_url = https://example.ru/offer")
    _series(flow, end + H, op="attendance", arg="1 attended")
    _, text = _series(flow, end + H, op="dispatch")
    assert "0 из 0" in text  # no opt-in yet
    _series(flow, end + H, op="offers_on", user_id="u2")
    _series(flow, end + H, op="dispatch")
    sent = flow.effects.sent[-2]
    assert sent["user_id"] == "u2" and "https://example.ru/offer" in sent["text"] and "/offers_off" in sent["text"]
    _series(flow, end + 25 * H, op="dispatch")
    assert "без искусственной срочности" in flow.effects.sent[-2]["text"]
    _series(flow, end + 25 * H, op="offers_off", user_id="u2")
    _, text = _series(flow, end + 49 * H, op="dispatch")
    assert "0 из 0" in text


def test_unknown_attendance_and_expired_window_send_nothing() -> None:
    from application.business_flows.bookings import Slot

    slot = Slot("s", "T", NOW, 60, "booked", "c")
    st = es.replay([es.consent("c", True)])
    assert es.due_messages(st, {"s": slot}, now_ms=NOW + 2 * H, offer_url="https://x") == []
    st.attendance[("s", "c")] = "no_show"
    assert len(es.due_messages(st, {"s": slot}, now_ms=NOW + 2 * H, offer_url="https://x")) == 1
    assert es.due_messages(st, {"s": slot}, now_ms=NOW + 5 * D, offer_url="https://x") == []


def test_owner_texts_validation_and_reset(flow) -> None:
    with pytest.raises(ValueError):
        es.set_text("warmup all 1 | Скидка по ссылке https://x")
    with pytest.raises(ValueError):
        es.set_text("followup attended_unpaid 1 | без ссылки")
    with pytest.raises(ValueError):
        es.set_text("followup no_show 3 | {offer}")
    _series(flow, NOW, op="text", arg="followup no_show 1 | Жаль, что не вышло: {offer}")
    _, text = _series(flow, NOW, op="preview")
    assert "followup no_show 1 (+1 ч, не пришли) [owner]: Жаль" in text
    _series(flow, NOW, op="reset", arg="followup no_show 1")
    assert "[owner]" not in _series(flow, NOW, op="preview")[1]
    _, text = _series(flow, NOW, op="warmup_days", arg="7, 1")
    assert "7, 1" in text


def test_attendance_only_for_past_bookings(flow) -> None:
    _book(flow)
    _, text = _series(flow, NOW, op="attendance", arg="1 attended")
    assert "Не получилось" in text


def test_channel_priority_and_pick():
    from application.business_flows import event_series as es
    assert es.channel_priority({}) == es.DEFAULT_CHANNEL_PRIORITY
    assert es.channel_priority({es.CHANNEL_PRIORITY_ENV: "Telegram, x, telegram,vk"}) == ("telegram", "vk")
    assert es.channel_priority({es.CHANNEL_PRIORITY_ENV: "bad"}) == es.DEFAULT_CHANNEL_PRIORITY
    assert es.pick_channel({"vk", "telegram"}, {"telegram"}, {}) == "telegram"
    assert es.pick_channel({"vk"}, {"telegram"}, {}) is None


def test_event_content_plan_and_visual_key():
    from application.business_flows import event_series as es
    f = [es.set_content_mode("e1", "warmup", "text_with_image")]
    plan = es.content_plan(es.replay(f), "e1")
    assert plan == {"warmup": "text_with_image", "event_day_announcement": "text", "post_event_followup": "text"}
    import pytest
    with pytest.raises(ValueError):
        es.set_content_mode("e1", "warmup", "gif")
    assert es.event_visual_idempotency_key(event_id="e1", stage="warmup", message_key="w:1") == "event:e1:warmup:w:1:image:v1"
    with pytest.raises(ValueError):
        es.event_visual_idempotency_key(event_id="e1", stage="warmup", message_key="bad key")
