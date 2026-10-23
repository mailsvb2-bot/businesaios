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


def test_slot_bound_to_offering_and_business_timezone(flow) -> None:
    from runtime.handler_impl.domains.business_flow_ops import handle_bookings

    run = partial(flow.run, H)
    run(op="offering_add", arg="individual | Разбор | 1:1")
    run(op="profile_set", arg="Студия | Asia/Yekaterinburg")
    book = partial(flow.run, partial(handle_bookings, now_ms=1_800_000_000_000))
    assert "не найдено" in book(op="add_slot", arg="2027-01-20 15:00 60 #2")[1]
    book(op="add_slot", arg="2027-01-20 15:00 60 #1")
    fact = flow.store.events[-1]["payload"]
    assert fact["title"] == "Разбор" and fact["offering_id"]
    from datetime import UTC, datetime

    assert fact["starts_at_ms"] == int(datetime(2027, 1, 20, 10, 0, tzinfo=UTC).timestamp() * 1000)


def test_payment_linked_to_customer() -> None:
    from application.business_flows import admin

    change, _ = admin.record_payment(admin.replay([]), "Разбор | 1500 RUB | P-1 | cust42")
    assert change["customer_id"] == "cust42"
    assert admin.replay([change]).payments[change["payment_id"]].customer_id == "cust42"
    plain, _ = admin.record_payment(admin.replay([]), "Разбор | 1500 RUB | P-2")
    assert "customer_id" not in plain


def test_rename_and_restore_offering():
    from application.business_flows import catalog as cg

    fmt = next(iter(cg.DEFAULT_ON))
    f = [cg.create_offering(cg.Catalog(), f"{fmt} | йога | утро")]
    c = cg.replay(f)
    r = cg.rename_offering(c, "1 | пилатес")
    assert (
        r["step"] == "offering_renamed"
        and cg.rename_offering(c, f"1 | {c.offerings[f[0]['offering_id']].title}") is None
    )
    f += [r, cg.retire_offering(cg.replay([*f, r]), "1")]
    c = cg.replay(f)
    assert not cg.active_offerings(c)
    f.append(cg.restore_offering(c, "1"))
    c = cg.replay(f)
    assert cg.active_offerings(c)[0].title == r["title"]


def test_offering_direction_bind_and_unbind() -> None:
    from application.business_flows import catalog as cg_

    facts = [cg_.create_direction(cg_.Catalog(), "Йога | утро")]
    c = cg_.replay(facts)
    c.formats.add(next(iter(cg_.FORMATS)))
    fmt = next(iter(c.formats))
    facts += [{"step": "format_toggled", "format": fmt, "enabled": True}, cg_.create_offering(c, f"{fmt} | Абонемент")]
    c = cg_.replay(facts)
    ch = cg_.bind_offering(c, "1 | 1")
    facts.append(ch)
    c = cg_.replay(facts)
    assert next(iter(c.offerings.values())).direction_id == ch["direction_id"]
    assert "Абонемент" in cg_.direction_text(c, "1")
    assert cg_.bind_offering(c, "1 | 1") is None
    facts.append(cg_.bind_offering(c, "1 | -"))
    assert next(iter(cg_.replay(facts).offerings.values())).direction_id is None


def test_profile_details_extract_review_confirm(flow) -> None:
    from application.business_flows import catalog as cg

    d = cg.extract_profile_details("Услуги: хатха, йога-нидра; Город: Казань\nЦены: от 1 500 ₽. Пишите @yoga_kzn или +7 900 123-45-67")
    assert d["services"] == ["хатха", "йога-нидра"] and d["geo"] == ["Казань"]
    assert d["prices"] == ["1 500 ₽"] and d["contacts"] == ["+7 900 123-45-67", "@yoga_kzn"]
    assert "audiences" not in d  # never guessed
    run = partial(flow.run, H)
    assert "ничего не распознано" in run(op="profile_details", arg="просто текст")[1]
    assert "сначала" in run(op="profile_confirm")[1]
    review = run(op="profile_details", arg="Услуги: хатха; Город: Казань")[1]
    assert "Я правильно понял" in review and "• Услуги: хатха" in review and "География: Казань" in review
    assert "не подтверждены" in run(op="profile")[1]
    assert "подтверждены." in run(op="profile_confirm")[1]
    assert "Уже" in run(op="profile_confirm")[1]
    assert "✅ Детали подтверждены" in run(op="profile")[1]
    run(op="profile_details", arg="Услуги: хатха, пилатес")  # new details reset confirmation
    assert "не подтверждены" in run(op="profile")[1]
