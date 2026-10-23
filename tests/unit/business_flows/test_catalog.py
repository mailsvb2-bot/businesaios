from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_business_admin as H


def test_directions_lifecycle_keeps_history(flow) -> None:
    run = partial(flow.run, H)
    assert "создано" in run(op="direction_add", arg="Йога | утренние группы")[1]
    assert "уже есть" in run(op="direction_add", arg="йога")[1]
    run(op="direction_goal", arg="1 | 20 учеников")
    run(op="direction_edit", arg="1 | Хатха-йога")
    run(op="offering_add", arg="group | Утро | 7:00 | 1")
    text = run(op="direction", arg="1")[1]
    assert "Хатха-йога" in text and "20 учеников" in text and "Утро (группа)" in text
    run(op="direction_archive", arg="1")
    assert "Пока пусто" in run(op="directions")[1]
    assert "Хатха-йога" in run(op="directions", arg="archived")[1]
    run(op="direction_restore", arg="1")
    assert "Хатха-йога" in run(op="directions")[1]


def test_offerings_and_formats(flow) -> None:
    run = partial(flow.run, H)
    assert "выключен" in run(op="offering_add", arg="online | Вебинар")[1]
    run(op="format_on", arg="online")
    assert "добавлено" in run(op="offering_add", arg="онлайн | Вебинар | zoom")[1]
    assert "активные предложения" in run(op="format_off", arg="online")[1]
    run(op="offering_retire", arg="1")
    assert "Пока пусто" in run(op="offerings")[1]
    assert "Уже так" not in run(op="format_off", arg="online")[1]
    assert "▫️ online" in run(op="formats")[1]


def test_business_profile(flow) -> None:
    run = partial(flow.run, H)
    assert "неизвестный" in run(op="profile_set", arg="Йога | Mars/Base")[1]
    run(op="profile_set", arg="Студия йоги | Asia/Yekaterinburg")
    text = run(op="profile")[1]
    assert "Студия йоги" in text and "Asia/Yekaterinburg" in text
