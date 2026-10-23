from __future__ import annotations

from functools import partial

from runtime.handler_impl.domains.business_flow_ops import handle_business_admin, handle_business_ops_summary

NOW = 1_800_000_000_000


def _screen(flow, data):
    flow.run(partial(handle_business_ops_summary, now_ms=NOW), op="cockpit", arg=data)
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return msg["text"], cbs


def test_refund_button_confirms_then_writes_one_refund_fact(flow) -> None:
    flow.run(handle_business_admin, op="price", arg="Разбор | 3000 RUB")
    flow.run(handle_business_admin, op="pay", arg="Разбор | 3000 RUB | SBP-778899")
    assert "cpm:payments:0" in _screen(flow, "cpm:money")[1]
    text, cbs = _screen(flow, "cpm:payments:0")
    assert "Разбор" in text and "…8899" in text and "SBP-778899" not in text
    text, cbs = _screen(flow, cbs[0])
    assert "Вернуть 3" in text and "деньги переводите сами" in text
    text, cbs = _screen(flow, cbs[0])
    assert "✅ Возврат записан" in text and "возвращено полностью" in text
    assert not any(c.startswith("cpm:pay-refund") for c in cbs)



def test_refund_is_idempotent_and_unknown_payment_is_refused(flow) -> None:
    flow.run(handle_business_admin, op="pay", arg="Разбор | 100 RUB | R1")
    pid = _screen(flow, "cpm:payments:0")[1][0].split(":")[-1]
    _screen(flow, f"cpm:pay-rf:{pid}")
    assert "уже записан" in _screen(flow, f"cpm:pay-rf:{pid}")[0]  # same refund ref replays, never doubles
    assert "Не получилось" in _screen(flow, "cpm:pay-rf:pay_nope")[0]


def test_prices_and_growth_report_are_honest_about_missing_data(flow) -> None:
    assert "Цен пока нет" in _screen(flow, "cpm:prices")[0]
    flow.run(handle_business_admin, op="price", arg="Разбор | 3000 RUB")
    assert "Разбор — 3" in _screen(flow, "cpm:prices")[0]
    text, _ = _screen(flow, "cpm:growth-report")
    assert "Обращения: 0" in text and "платежей не записано" in text and "атрибуции" in text
    assert "cpm:growth-report" in _screen(flow, "cpm:growth")[1]
