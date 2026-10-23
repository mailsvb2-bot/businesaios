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
    assert "Шаг 1/4" in text
    cbs = _buttons(flow.effects.sent[-1])
    assert cbs[0] == "cpe:20270116" and len(cbs) == 14 and all(len(c) <= 64 for c in cbs)
    run(op="wizard", arg="cpe:20270116")
    assert "cpe:20270116:1500" in _buttons(flow.effects.sent[-1])
    run(op="wizard", arg="cpe:20270116:1500")
    run(op="wizard", arg="cpe:20270116:1500:90")
    assert "cpe:20270116:1500" in _buttons(flow.effects.sent[-1])  # back button
    _, text = run(op="wizard", arg="cpe:20270116:1500:90:31")
    assert "Слот открыт" in text and "90 мин" in text
    slots = bk.replay([e["payload"] for e in flow.store.events if e["event_type"] == "bookings@v1"])
    (slot,) = slots.values()
    assert slot.title == "Разбор воронки" and slot.duration_min == 90
    st = es.replay([e["payload"] for e in flow.store.events if e["event_type"] == "event_series@v1"])
    assert st.warmup_days == (3, 1)
    _, text = run(op="wizard", arg="cpe:20270116:1500:90:31")
    assert "wizard_no_draft" in text  # finished draft cannot replay a second slot


def test_wizard_rejects_forged_choices() -> None:
    with pytest.raises(ValueError):
        wz.step("T", "cpe:20270116:0300:90:31", now_ms=NOW)
    with pytest.raises(ValueError):
        wz.step("T", "cpe:20200101:1500:90:0", now_ms=NOW)
    with pytest.raises(ValueError):
        wz.draft("u", "  ")


def test_wizard_callbacks_owner_only() -> None:
    from types import SimpleNamespace

    ctx = SimpleNamespace(callback_data="cpe:20270116", is_admin=False, cmd="", args="")
    assert handle_business_flow_routes(ctx, user_id="u") is None
