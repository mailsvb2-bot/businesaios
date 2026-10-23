from __future__ import annotations

from functools import partial

import pytest

from application.business_flows import publications as pb
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin

NOW = 1_800_000_000_000  # 2027-01-15 11:00 МСК


def test_calendar_lifecycle(flow) -> None:
    run = partial(flow.run, partial(handle_business_admin, now_ms=NOW))
    assert "Черновик сохранён" in run(op="post_add", arg="vk Анонс | Встреча в пятницу")[1]
    assert "уже есть" in run(op="post_add", arg="vk Анонс | Встреча в пятницу")[1]
    assert "Не получилось" in run(op="post_schedule", arg="1 2020-01-01 10:00")[1]
    assert "16.01 10:00" in run(op="post_schedule", arg="1 2027-01-16 10:00")[1]
    text = run(op="posts", arg="")[1]
    assert "ВКонтакте · Запланирована · Анонс" in text and "Пора" not in text
    run(op="post_publish", arg="1")
    assert "Опубликована" in run(op="posts", arg="")[1]
    assert "Не получилось" in run(op="post_unschedule", arg="1")[1]
    run(op="post_retire", arg="1")
    assert "Уже в архиве" in run(op="post_retire", arg="1")[1]


def test_due_and_validation() -> None:
    pubs = pb.replay(
        [
            {"step": "pub_draft", "pub_id": "p", "channel": "telegram", "title": "T", "body": "B", "at_ms": 0},
            {"step": "pub_scheduled", "pub_id": "p", "at_ms": NOW - 1},
        ]
    )
    assert [p.pub_id for p in pb.due(pubs, now_ms=NOW)] == ["p"]
    with pytest.raises(ValueError):
        pb.draft({}, "Без текста", now_ms=NOW)
    with pytest.raises(ValueError):
        pb.transition(pubs, "publish", "9", now_ms=NOW)
    assert pb.calendar_lines({}) == ["• Публикаций пока нет."]


def test_cockpit_callback_carries_ack_once(flow) -> None:
    from types import SimpleNamespace

    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes

    ctx = SimpleNamespace(callback_data="cpm:menu", callback_query_id="q1", is_admin=True, cmd="", args="")
    assert handle_business_flow_routes(ctx, user_id="u").payload["callback_query_id"] == "q1"
