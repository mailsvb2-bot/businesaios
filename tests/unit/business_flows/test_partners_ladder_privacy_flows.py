from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import ladder as ld
from application.business_flows import partners as pt
from runtime.handler_impl.domains.business_flow_ops import handle_bookings, handle_offer_ladder, handle_partners
from runtime.handler_impl.domains.user_ops import handle_privacy_delete

NOW = 1_800_000_000_000


def test_partner_search_ranks_by_audience_and_flags_contact_basis(flow) -> None:
    flow.run(handle_partners, op="add", arg="Кофейня Зерно | кофе, завтраки, москва | 9000 | existing | @zerno")
    flow.run(handle_partners, op="add", arg="Фитнес Пульс | спорт, зал | 7000 | public | info@pulse.ru")
    flow.run(handle_partners, op="add", arg="Кофе Конкурент | кофе | 8000 | opted_in | @rival | competitor")
    out, text = flow.run(handle_partners, op="rank", arg="кофе завтраки")
    assert out["ok"] and text.index("Кофейня Зерно") < text.index("Фитнес Пульс")
    assert "прямой конкурент" in text and "только подготовить предложение" in text
    assert "ничего не отправляется" in text
    assert "Не получилось" in flow.run(handle_partners, op="add", arg="X | y | 1 | spam")[1]


def test_partner_score_is_bounded() -> None:
    p = pt.replay([pt.parse_partner("A | a | 50000000 | none | ")]).popitem()[1]
    assert 0.0 <= pt.score(p, ["a"]).total <= 100.0


def test_offer_ladder_unlocks_steps_by_evidence(flow) -> None:
    flow.run(handle_offer_ladder, op="add", arg="diagnostic | Экспресс-диагностика | 0")
    flow.run(handle_offer_ladder, op="add", arg="implementation | Внедрение воронки | 0,7")
    _, low = flow.run(handle_offer_ladder, op="show", arg="0.3")
    assert "Экспресс-диагностика" in low and "Внедрение" not in low and "подтверждение" in low
    assert "Внедрение воронки" in flow.run(handle_offer_ladder, op="show", arg="0.9")[1]
    with pytest.raises(ValueError):
        ld.parse_step("upsell | x | 0.1", position=1)


def test_participant_home_and_pd_deletion_reopens_slot(flow) -> None:
    run = partial(flow.run, partial(handle_bookings, now_ms=NOW))
    flow.store.events.append(
        {
            "tenant_id": "t1",
            "user_id": "owner",
            "event_type": "bookings@v1",
            "timestamp_ms": -1,
            "payload": {
                "step": "slot_opened",
                "slot_id": "s1",
                "title": "Сессия",
                "starts_at_ms": NOW + 86_400_000 * 3,
                "duration_min": 60,
            },
        }
    )
    run(op="book", arg="1")
    assert "Ближайшая запись" in run(op="home")[1]
    _, ask = flow.run(handle_privacy_delete, op="request", arg="")
    assert "необратимо" in ask and not any(e["event_type"] == "privacy_deleted@v1" for e in flow.store.events)
    out, done = flow.run(handle_privacy_delete, op="request", arg="подтверждаю")
    assert out["ok"] and "удалено записей — 1" in done
    receipt = flow.store.events[-1]
    assert receipt["event_type"] == "privacy_deleted@v1" and "u1" not in str(receipt["payload"])
    assert "1. " in run(op="list")[1]  # booking gone with the user's events -> slot open again


def test_owner_ops_summary_counts_projections(flow) -> None:
    from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary

    run = partial(flow.run, partial(handle_bookings, now_ms=NOW))
    run(op="add_slot", arg="2027-01-20 15:00 Сессия")
    run(op="add_slot", arg="2027-01-21 15:00 Сессия")
    run(op="book", arg="1")
    flow.run(handle_partners, op="add", arg="A | a | 10 | existing | @a")
    out, text = flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="show")
    assert out["ok"] and "Слоты впереди: 2 (занято 1, свободно 1)" in text and "Партнёров в базе: 1" in text
