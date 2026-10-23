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
