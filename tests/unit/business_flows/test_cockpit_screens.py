from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import (
    handle_bookings,
    handle_business_admin,
    handle_business_ops_summary,
    handle_event_series,
)

NOW = 1_800_000_000_000
H = 3_600_000


def _screen(flow, data, now=NOW):
    flow.run(partial(handle_business_ops_summary, now_ms=now), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return msg["text"], cbs


def _seed(flow):
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg="2027-01-20 15:00 60 Разбор")
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="cust-000042")
    flow.run(handle_business_admin, op="price", arg="Разбор | 1500 RUB")
    flow.run(handle_business_admin, op="pay", arg="Разбор | 1500 RUB | ch-1")
    flow.run(partial(handle_event_series, now_ms=NOW), op="offers_on", user_id="cust-000042")


def test_work_and_manage_menus_link_new_screens(flow) -> None:
    _, cbs = _screen(flow, "cpm:work")
    assert {"cpm:calendar", "cpm:customers:0", "cpm:events", "cpm:money"} <= set(cbs)
    _, cbs = _screen(flow, "cpm:manage")
    assert {"cpm:services", "cpm:automation", "cpm:settings"} <= set(cbs)


def test_money_services_settings_automation(flow) -> None:
    _seed(flow)
    text, cbs = _screen(flow, "cpm:money")
    assert "1 шт." in text and "cpm:work" in cbs
    assert "Разбор" in _screen(flow, "cpm:services")[0]
    assert "Автопилот: выключен" in _screen(flow, "cpm:automation")[0]
    assert "Настроек нет" in _screen(flow, "cpm:settings")[0]


def test_customers_detail_calendar_events(flow) -> None:
    _seed(flow)
    text, cbs = _screen(flow, "cpm:customers:0")
    assert "000042 — записей: 1" in text and "cpm:customer:cust-000042" in cbs
    text, cbs = _screen(flow, "cpm:customer:cust-000042")
    assert "согласен" in text and "впереди" in text and "cpm:customers:0" in cbs
    assert "Эта кнопка уже неактуальна" in _screen(flow, "cpm:customer:nobody")[0]
    assert "занято" in _screen(flow, "cpm:calendar")[0]
    text, _ = _screen(flow, "cpm:events", now=NOW + 7 * 24 * H)
    assert "Согласны на предложения: 1" in text and "без отметки посещения: 1" in text


def test_customer_card_routes_current_action_and_masks_contact(flow) -> None:
    from application.business_flows import cockpit as cpk

    _seed(flow)
    text, cbs = _screen(flow, "cpm:customer:cust-000042", now=NOW + 7 * 24 * H)
    assert "Сейчас: Отметить посещение" in text and "cpm:ev-conduct" in cbs
    text, cbs = _screen(flow, "cpm:customer:cust-000042")
    assert "Сейчас:" not in text and "cpm:ev-conduct" not in cbs
    assert cpk.safe_contact("phone", subject="+79991234567") == "Телефон: •••• 4567"
    assert cpk.safe_contact("email", subject="a@b.ru") == "Email: •••@b.ru"
    assert cpk.safe_contact("telegram", username="anna") == "Telegram: @anna"
    assert cpk.safe_contact("internal") is None


def test_customer_search_and_archive_hide_but_keep_history(flow) -> None:
    _seed(flow)
    flow.run(partial(handle_bookings, now_ms=NOW), op="add_slot", arg="2027-01-21 15:00 60 Разбор")
    flow.run(partial(handle_bookings, now_ms=NOW), op="book", arg="1", user_id="cust-000777")
    text, _ = _screen(flow, "cpm:customers:000777")
    assert "000777" in text and "000042" not in text
    assert "Никого не найдено" in _screen(flow, "cpm:customers:zzz")[0]
    flow.run(handle_business_admin, op="customer_archive", arg="cust-000042")
    assert "скрыт из списка" in flow.effects.sent[-1]["text"]
    flow.run(handle_business_admin, op="customer_archive", arg="cust-000042")
    assert "без изменений" in flow.effects.sent[-1]["text"]
    assert "000042" not in _screen(flow, "cpm:customers:0")[0]
    assert "000042" in _screen(flow, "cpm:customer:cust-000042")[0]  # history intact
    flow.run(handle_business_admin, op="customer_archive", arg="nobody")
    assert "customer_unknown" in flow.effects.sent[-1]["text"]
    flow.run(handle_business_admin, op="customer_archive", arg="cust-000042 off")
    assert "000042" in _screen(flow, "cpm:customers:0")[0]


def test_customers_command_routes_to_search_screen() -> None:
    from types import SimpleNamespace

    from core.policies.telegram.routes import business_flow_routes as r

    def ctx(args, admin=True):
        return SimpleNamespace(cmd="/customers", args=args, is_admin=admin, callback_data="", callback_query_id="",
                               session={}, text="/customers " + args)  # fmt: skip

    assert r.handle_business_flow_routes(ctx("x", admin=False), user_id="1") is None
    act = r.handle_business_flow_routes(ctx("0777;drop"), user_id="1")
    assert act is not None and "cpm:customers:0777drop" in str(act)
    assert r.BUSINESS_FLOW_COMMANDS["/customer_archive"] == ("business_admin@v1", "customer_archive", True)


def test_calendar_management_lists_timezone_and_sorted_offerings(flow) -> None:
    text = _screen(flow, "cpm:calendar")[0]
    assert "Часовой пояс: Europe/Moscow" in text and "/offering_add" in text
    flow.run(handle_business_admin, op="offering_add", arg="individual | Яблоко | x")
    flow.run(handle_business_admin, op="offering_add", arg="individual | банан | y")
    text = _screen(flow, "cpm:calendar")[0]
    assert text.index("#1 банан") < text.index("#2 Яблоко")


def test_attribution_spine_and_revenue_attribution_pure() -> None:
    from application.business_flows import promotions as pm

    bk = [(1, {"step": "promotion_saved", "promotion_id": "pr1", "slot_id": "s1", "channel": "vk", "source_token": "t"}),
          (2, {"step": "promotion_opened", "promotion_id": "pr1", "slot_id": "s1", "customer_id": "c1"}),
          (3, {"step": "booked", "promotion_id": "pr1", "slot_id": "s1", "customer_id": "c1"}),
          (4, {"step": "booked", "slot_id": "s2", "customer_id": "c2"}),
          (9, {"step": "promotion_opened", "promotion_id": "pr1", "slot_id": "s1", "customer_id": "c3"})]
    adm = [(5, {"step": "payment_recorded", "payment_id": "p1", "offering": "x", "amount_minor": 150000,
                "currency": "RUB", "reference": "r", "customer_id": "c1"}),
           (6, {"step": "payment_recorded", "payment_id": "p2", "offering": "x", "amount_minor": 50000,
                "currency": "RUB", "reference": "r2", "customer_id": "c3"}),
           (7, {"step": "payment_refunded", "payment_id": "p1", "refund_id": "f1", "amount_minor": 10000})]
    assert pm.customer_trace(bk, "c1")["at_ms"] == 2 and pm.customer_trace(bk, "c2") is None
    assert pm.booking_trace(bk, "s1")["channel"] == "vk" and pm.booking_trace(bk, "s2") is None
    outs = pm.outcomes(adm, bk)
    assert [o["id"] for o in outs[:2]] == ["f1", "p2"] and outs[0]["currency"] == "RUB"
    assert [o["id"] for o in pm.outcomes(adm, bk, outcome_type="booking", customer_id="c2")] == ["s2"]
    assert pm.attribute_outcome(adm, bk, "p1")["channel"] == "vk"
    late = pm.attribute_outcome(adm, bk, "p2")  # c3 touched only after paying
    assert late["channel"] == "unattributed" and late["reason"] == "no_touch_before_outcome"
    assert pm.attribute_outcome(adm, bk, "nope") is None
    e = pm.unit_economics(adm, bk, occurred_from=0, occurred_to=100)
    assert e["net_minor"] == 190000 and e["roas"] is None and e["limitations"] == ["spend_not_verified"]
    assert e["revenue_by_channel_minor"] == {"unattributed": 50000, "vk": 140000}
    v = pm.unit_economics(adm, bk, occurred_from=0, occurred_to=100, verified_spend=(95000, "RUB"))
    assert v["roas"] == 2.0 and v["cac_minor"] == 47500
    assert pm.unit_economics(adm, bk, occurred_from=0, occurred_to=100, verified_spend=(1, "USD"))["roas"] is None
    j = pm.revenue_journey(adm, bk, occurred_from=0, occurred_to=100)
    assert (j["touched"], j["booked"], j["paid"], j["touched_then_paid"]) == (2, 2, 2, 2)


def test_revenue_screens_route(flow) -> None:
    _seed(flow)
    for op in ("outcomes", "economics", "journey"):
        flow.run(partial(handle_business_ops_summary, now_ms=NOW), op=op, arg="")
    texts = [m["text"] for m in flow.effects.sent[-3:]]
    assert "payment" in texts[0] and "ROAS/CAC не считаются" in texts[1] and "Путь клиента" in texts[2]
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="trace", arg="cust-000042")
    assert "нет атрибутированного" in flow.effects.sent[-1]["text"]
