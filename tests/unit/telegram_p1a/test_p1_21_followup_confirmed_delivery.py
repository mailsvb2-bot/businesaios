"""P1-21: a sales follow-up counts as sent only after the provider confirmed it."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial

from application.business_flows import sales as sl
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

NOON = int(datetime(2027, 3, 1, 9, 0, tzinfo=UTC).timestamp() * 1000)  # 12:00 MSK
H = 3_600_000


def _state(flow):
    return next(iter(sl.replay([e["payload"] for e in flow.store.events]).leads.values()))


def _planned(flow):
    sales = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOON))
    sales(op="inbound", arg="Привет", reply="ok", user_id="cust1")  # consent: the customer wrote first
    sales(op="followup_plan", arg="1 | 1 | Напоминаю о записи")  # owner-approved text and time
    return partial(flow.run, partial(handle_sales_pipeline, now_ms=NOON + 2 * H))


def _failing_customer_sends(flow, monkeypatch):
    original = flow.effects.send_message

    def send(**kw):
        if kw["user_id"] == "cust1":
            original(**kw)  # like the real effects: a tracked fact is recorded even on failure
            return {"ok": False, "meta": {"reason": "telegram_forbidden"}}
        return original(**kw)

    monkeypatch.setattr(flow.effects, "send_message", send)


def test_flag_off_keeps_legacy_behaviour(flow, monkeypatch):
    monkeypatch.delenv("BAI_SALES_FOLLOWUP_CONFIRMED_DELIVERY", raising=False)
    later = _planned(flow)
    _failing_customer_sends(flow, monkeypatch)
    later(op="followup_dispatch")
    assert not _state(flow).followup_id  # legacy: marked sent although not delivered (the gap)


def test_confirmed_delivery_records_sent_with_receipt(flow, monkeypatch):
    monkeypatch.setenv("BAI_SALES_FOLLOWUP_CONFIRMED_DELIVERY", "1")
    later = _planned(flow)
    _, text = later(op="followup_dispatch")
    customer = [m for m in flow.effects.sent if m["user_id"] == "cust1" and m["text"] != "ok"]
    assert [m["text"] for m in customer] == ["Напоминаю о записи"] and not customer[0].get("track_event_type")
    facts = [e["payload"] for e in flow.store.events if e["payload"].get("step") == "followup_sent"]
    assert len(facts) == 1 and facts[0]["delivery_ref"]
    assert "доставлено: 1 из 1" in text and not _state(flow).followup_id


def test_failed_delivery_is_retried_then_dropped_never_reported_as_sent(flow, monkeypatch):
    monkeypatch.setenv("BAI_SALES_FOLLOWUP_CONFIRMED_DELIVERY", "1")
    later = _planned(flow)
    _failing_customer_sends(flow, monkeypatch)
    _, text = later(op="followup_dispatch")
    assert "доставлено: 0 из 1" in text
    lead = _state(flow)
    assert lead.followup_id and lead.followup_attempts == 1  # still queued
    sales = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOON))
    assert "Не доставлено попыток: 1 из 3" in sales(op="followup", arg="1")[1]
    later(op="followup_dispatch")
    later(op="followup_dispatch")
    lead = _state(flow)
    assert not lead.followup_id and lead.followup_attempts == 0
    steps = [e["payload"]["step"] for e in flow.store.events if e["payload"].get("step", "").startswith("followup_")]
    assert steps.count("followup_failed") == 3 and "followup_sent" not in steps
    assert any("напоминание снято" in m["text"] for m in flow.effects.sent)
    assert "0 из 0" in later(op="followup_dispatch")[1]


def test_quiet_hours_and_optout_still_apply(flow, monkeypatch):
    monkeypatch.setenv("BAI_SALES_FOLLOWUP_CONFIRMED_DELIVERY", "1")
    _planned(flow)
    night = int(datetime(2027, 3, 1, 20, 0, tzinfo=UTC).timestamp() * 1000)  # 23:00 MSK
    assert "тихие часы" in flow.run(partial(handle_sales_pipeline, now_ms=night), op="followup_dispatch")[1]
    flow.run(partial(handle_sales_pipeline, now_ms=NOON), op="optout", arg="1 | подтвердить")
    assert "0 из 0" in flow.run(partial(handle_sales_pipeline, now_ms=NOON + 2 * H), op="followup_dispatch")[1]
