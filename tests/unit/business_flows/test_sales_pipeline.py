from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import sales as sl
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

NOW = 1_800_000_000_000
S = sl.Stage


def test_reducer_matches_donor_semantics() -> None:
    assert sl.reduce(S.DISCOVERED, "contact") == S.ENGAGED
    assert sl.reduce(S.QUALIFIED, "need") == S.QUALIFIED  # repeated milestone is idempotent
    with pytest.raises(ValueError):
        sl.reduce(S.ENGAGED, "offer")  # no skipping
    assert sl.reduce(S.ENGAGED, "paid") == S.WON
    assert sl.reduce(S.WON, "declined") == S.WON
    assert sl.reduce(S.OFFER_PRESENTED, "handoff") == S.OFFER_PRESENTED
    with pytest.raises(ValueError):
        sl.reduce(S.LOST, "contact")


def test_pipeline_flow(flow) -> None:
    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    assert "Лид добавлен" in run(op="add", arg="Анна | Instagram")[1]
    assert "уже есть" in run(op="add", arg="анна | instagram")[1]
    assert "на связи" in run(op="event", arg="1 contact")[1]
    assert "Не получилось" in run(op="event", arg="1 checkout")[1]
    run(op="event", arg="1 handoff")
    assert "нужен человек" in run(op="list")[1]
    run(op="event", arg="1 resume")
    assert "нужен человек" not in run(op="list")[1]
    run(op="next", arg="1 | 2027-01-15 12:00 | позвонить")
    run(op="note", arg="1 | хочет групповой формат")
    assert "групповой" in run(op="card", arg="1")[1]
    assert "позвонить" in partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW + 10 * 3_600_000))(op="due")[1]
    run(op="event", arg="1 declined")
    assert "отказ" in run(op="list")[1]
    assert "снова в работе" in run(op="reopen", arg="1")[1]
    assert "Воронка: на связи: 1" in run(op="list")[1]


def test_assignment_claim_and_clear_next(flow) -> None:
    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=NOW))
    run(op="add", arg="Борис | VK")
    assert "assignee_not_member" in run(op="assign", arg="1 999")[1]
    assert "handoff_not_open" in run(op="claim", arg="1")[1]
    run(op="event", arg="1 handoff")
    assert "Ждут человека: 1" in run(op="handoffs")[1]
    assert "разговор у Вас" in run(op="claim", arg="1")[1]
    assert "ведёт" in run(op="list")[1]
    assert "(уже)" in run(op="claim", arg="1")[1]
    assert "ответственный снят" in run(op="assign", arg="1 -")[1]
    assert "Без изменений" in run(op="assign", arg="1 -")[1]
    run(op="next", arg="1 | 2027-01-15 12:00 | позвонить")
    assert "снят" in run(op="next", arg="1 -")[1]
    assert "не было" in run(op="next", arg="1 -")[1]
    assert "дальше" not in run(op="list")[1]


def test_claim_rejects_other_owner() -> None:
    st = sl.replay(
        [
            {"step": "lead_added", "lead_id": "l1", "name": "A"},
            {"step": "lead_event", "lead_id": "l1", "event": "handoff", "stage": "discovered"},
            {"step": "lead_assigned", "lead_id": "l1", "assignee": "7"},
        ]
    )
    with pytest.raises(ValueError, match="already_claimed"):
        sl.claim_handoff(st, "1", user_id="8")
    assert sl.claim_handoff(st, "1", user_id="7") is None
    assert [x.lead_id for x in sl.handoff_work(st)] == ["l1"]
