from datetime import UTC, datetime
from functools import partial

import pytest

from application.business_flows import sales as sl
from application.business_flows import sales_followups as sf
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

NOON = int(datetime(2027, 3, 1, 9, 0, tzinfo=UTC).timestamp() * 1000)  # 12:00 MSK
H = 3_600_000


def _lead(**kw):
    return sl.Lead("l1", "Анна", "telegram", sl.Stage.ENGAGED, customer_id="c1", **kw)


def test_night_shift_and_status() -> None:
    late = int(datetime(2027, 3, 1, 20, 0, tzinfo=UTC).timestamp() * 1000)  # 23:00 MSK
    assert sf.shift_out_of_night(late, "Europe/Moscow") == int(
        datetime(2027, 3, 2, 5, 0, tzinfo=UTC).timestamp() * 1000
    )
    assert sf.shift_out_of_night(NOON, "Europe/Moscow") == NOON
    assert "больше не писать" in sf.status(_lead(followup_suppressed=True))
    assert "недоступно" in sf.status(sl.Lead("l2", "Б", "manual", sl.Stage.ENGAGED))


def test_plan_cancel_optout_and_inbound_stop(flow) -> None:
    sales = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOON))
    sales(op="inbound", arg="Привет", reply="ok", user_id="cust1")
    assert "недоступно" not in sales(op="followup", arg="1")[1]
    assert "1, 24 или 72" in sales(op="followup_plan", arg="1 | 5 | Текст")[1]
    sales(op="followup_plan", arg="1 | 1 | Напоминаю о записи")
    assert "уже запланировано" in sales(op="followup_plan", arg="1 | 1 | ещё")[1]
    st = sl.replay([e["payload"] for e in flow.store.events])
    (lead,) = st.leads.values()
    assert lead.followup_due_ms == NOON + H
    later = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOON + 2 * H))
    later(op="followup_dispatch")
    assert flow.effects.sent[-2]["user_id"] == "cust1" and flow.effects.sent[-2]["text"] == "Напоминаю о записи"
    assert "0 из 0" in later(op="followup_dispatch")[1]
    sales(op="followup_plan", arg="1 | 24 | Ещё раз")
    st = sl.replay([e["payload"] for e in flow.store.events])
    assert next(iter(st.leads.values())).followup_id
    assert "подтвердите" in sales(op="optout", arg="1")[1]
    sales(op="optout", arg="1 | подтвердить")
    st = sl.replay([e["payload"] for e in flow.store.events])
    lead = next(iter(st.leads.values()))
    assert lead.followup_suppressed and not lead.followup_id
    with pytest.raises(ValueError):
        sf.plan(st, "1 | 1 | x", now_ms=NOON, tz="Europe/Moscow")


def test_customer_reply_cancels_pending_followup() -> None:
    planned = {"step": "followup_planned", "lead_id": "l1", "followup_id": "f", "due_ms": 1, "text": "x"}
    added = {
        "step": "lead_inbound",
        "lead_id": "l1",
        "name": "А",
        "source": "telegram",
        "customer_id": "c",
        "dedupe_key": "k1",
    }
    reply = {**added, "dedupe_key": "k2"}
    assert not sl.replay([added, planned, reply]).leads["l1"].followup_id
