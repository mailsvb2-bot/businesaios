from __future__ import annotations

from functools import partial
from types import SimpleNamespace

import pytest

from application.business_flows import event_series as es
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000
H = es.HOUR_MS


def _slot():
    return SimpleNamespace(
        slot_id="s1", customer_id="c1", status="booked", starts_at_ms=NOW - 3 * H, duration_min=60, title="T"
    )


def _state(*extra):
    return es.replay(
        [
            {"step": "offers_consent", "customer_id": "c1", "on": True},
            {"step": "attendance", "slot_id": "s1", "customer_id": "c1", "status": "no_show"},
            *extra,
        ]
    )


def test_switches_gate_due_followups_at_dispatch_time() -> None:
    due = partial(es.due_messages, slots={"s1": _slot()}, now_ms=NOW, offer_url="https://x.ru")
    assert [m["kind"] for m in due(_state())] == ["followup"]
    assert due(_state({"step": "followups_toggle", "on": False})) == []
    assert due(_state({"step": "followup_segment", "segment": "no_show", "on": False})) == []
    assert due(
        _state(
            {"step": "followup_segment", "segment": "no_show", "on": False},
            {"step": "followup_segment", "segment": "no_show", "on": True},
        )
    )


def test_last_segment_cannot_be_disabled_while_on() -> None:
    st = _state({"step": "followup_segment", "segment": "attended_unpaid", "on": False})
    with pytest.raises(ValueError, match="last_segment"):
        es.followup_settings(st, "no_show off")
    st = _state(
        {"step": "followups_toggle", "on": False},
        {"step": "followup_segment", "segment": "attended_unpaid", "on": False},
    )
    es.followup_settings(st, "no_show off")
    with pytest.raises(ValueError):
        es.followup_settings(st, "email on")


def test_followups_command(flow) -> None:
    run = partial(flow.run, partial(handle_event_series, now_ms=NOW))
    assert "включены" in run(op="followups", arg="")[1]
    text = run(op="followups", arg="no_show off")[1]
    assert "не пришли (no_show): нет" in text
    assert "выключены" in run(op="followups", arg="off")[1]
    st = es.replay([e["payload"] for e in flow.store.events if e["event_type"] == "event_series@v1"])
    assert not st.followups_on and st.segments_off == {"no_show"}
