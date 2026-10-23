from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import bookings as bk
from application.business_flows import event_series as es
from application.business_flows import event_wizard as wz
from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000  # 2027-01-15 11:00 МСК


def _buttons(msg):
    return [b["callback_data"] for row in msg["reply_markup"]["inline_keyboard"] for b in row]


def test_wizard_walks_four_steps_and_opens_slot_with_warmup(flow) -> None:
    run = partial(flow.run, partial(handle_event_series, now_ms=NOW))
    _, text = run(op="wizard_start", arg="Разбор воронки")
    assert "Шаг 1/6" in text
    cbs = _buttons(flow.effects.sent[-1])
    assert cbs[0] == "cpe:20270116" and len(cbs) == 14 and all(len(c) <= 64 for c in cbs)
    run(op="wizard", arg="cpe:20270116")
    assert "cpe:20270116:1500" in _buttons(flow.effects.sent[-1])
    run(op="wizard", arg="cpe:20270116:1500")
    run(op="wizard", arg="cpe:20270116:1500:90")
    assert "cpe:20270116:1500" in _buttons(flow.effects.sent[-1])  # back button
    run(op="wizard", arg="cpe:20270116:1500:90:31")
    assert "cpe:20270116:1500:90:31:off" in _buttons(flow.effects.sent[-1])
    run(op="wizard", arg="cpe:20270116:1500:90:31:on")
    assert "cpe:20270116:1500:90:31:on:3" in _buttons(flow.effects.sent[-1])
    run(op="wizard", arg="cpe:20270116:1500:90:31:on:2")
    texts = [m["text"] for m in flow.effects.sent[-4:]]
    assert any("Слот открыт" in t and "90 мин" in t for t in texts) and "/event_place" in texts[-1]
    slots = bk.replay([e["payload"] for e in flow.store.events if e["event_type"] == "bookings@v1"])
    assert len(slots) == 2 and {s.title for s in slots.values()} == {"Разбор воронки"}
    assert all(s.duration_min == 90 for s in slots.values())
    st = es.replay([e["payload"] for e in flow.store.events if e["event_type"] == "event_series@v1"])
    assert st.warmup_days == (3, 1)
    _, text = run(op="wizard", arg="cpe:20270116:1500:90:31:on:2")
    assert "wizard_no_draft" in text  # finished draft cannot replay a second slot


def test_wizard_rejects_forged_choices() -> None:
    with pytest.raises(ValueError):
        wz.step("T", "cpe:20270116:0300:90:31:on:1", now_ms=NOW)
    with pytest.raises(ValueError):
        wz.step("T", "cpe:20270116:1500:90:31:tv:1", now_ms=NOW)
    with pytest.raises(ValueError):
        wz.step("T", "cpe:20200101:1500:90:0:off:1", now_ms=NOW)
    with pytest.raises(ValueError):
        wz.draft("u", "  ")


def test_wizard_callbacks_owner_only() -> None:
    from types import SimpleNamespace

    ctx = SimpleNamespace(callback_data="cpe:20270116", is_admin=False, cmd="", args="")
    assert handle_business_flow_routes(ctx, user_id="u") is None


def test_place_online_https_only_offline_address(flow) -> None:
    run = partial(flow.run, partial(handle_event_series, now_ms=NOW))
    run(op="wizard_start", arg="Йога")
    for cb in (
        "cpe:20270116",
        "cpe:20270116:1500",
        "cpe:20270116:1500:60",
        "cpe:20270116:1500:60:0",
        "cpe:20270116:1500:60:0:on",
    ):
        run(op="wizard", arg=cb)
    run(op="wizard", arg="cpe:20270116:1500:60:0:on:1")
    assert "Комната" not in run(op="place", arg="Йога | http://x.example")[1]
    assert "Комната: https://telemost.yandex.ru/j/1" in run(op="place", arg="Йога | https://telemost.yandex.ru/j/1")[1]
    assert "Площадка: ул. Ленина, 1" in run(op="place", arg="Чай | ул. Ленина, 1")[1]


def test_wizard_field_helpers() -> None:
    assert wz.parse_session_count("два дня") == 2 and wz.parse_session_count("5 дн.") == 5
    with pytest.raises(ValueError):
        wz.parse_session_count("40")
    assert wz.normalize_event_timezone("мск") == "Europe/Moscow"
    assert wz.normalize_event_timezone("Asia/Yekaterinburg") == "Asia/Yekaterinburg"
    with pytest.raises(ValueError):
        wz.normalize_event_timezone("Mars/Base")
    assert wz.normalize_session_join_url("позже") is None
    with pytest.raises(ValueError):
        wz.normalize_session_join_url("https://a", existing_urls=("https://a",))
    a = {"starts_at_ms": 0, "duration_min": 60}
    with pytest.raises(ValueError):
        wz.validate_session_sequence({"starts_at_ms": 1000, "duration_min": 60}, previous=a)
    with pytest.raises(ValueError):
        wz.place_fact("Йога", "https://x", mode="off")
