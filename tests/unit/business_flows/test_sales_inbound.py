import pytest

from application.business_flows import sales as sl
from application.business_flows import sales_inbound as si


def _rec(payloads, eid="1", text="Хочу записаться", ai=False):
    return si.record_message(
        payloads,
        channel="telegram",
        subject="42",
        name="Анна",
        source_ref="bot1",
        event_id=eid,
        text=text,
        ai_allowed=ai,
    )


def test_extract_and_normalize() -> None:
    assert si.extract_text({"message": {"text": "  привет\n мир "}}) == "привет мир"
    assert si.extract_text({"edited_message": {"caption": "фото"}}) == "фото"
    assert si.extract_text({"message": {"text": "/start"}}) is None
    assert si.extract_text({"callback_query": {}}) is None
    with pytest.raises(ValueError):
        si.printable("a\x01", field_name="x", maximum=5)


def test_inbound_creates_engaged_lead_idempotently_without_text_unless_ai() -> None:
    first = [_rec([])]
    (lead,) = sl.replay(first).leads.values()
    assert lead.stage == sl.Stage.ENGAGED and lead.source == "telegram" and not lead.notes
    assert _rec(first) is None
    second = _rec(first, eid="2", ai=True)
    (lead,) = sl.replay([*first, second]).leads.values()
    assert lead.notes == ("💬 Хочу записаться",)
    with pytest.raises(ValueError):
        _rec([], text="/help")
    with pytest.raises(ValueError):
        si.record_message(
            [], channel="email", subject="1", name="", source_ref="s", event_id="e", text="x", ai_allowed=False
        )


def test_handler_inbound_records_lead_and_replies(flow) -> None:
    from functools import partial

    from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

    run = partial(flow.run, handle_sales_pipeline)
    _, text = run(op="inbound", arg="Сколько стоит?", reply="Я здесь.", user_id="cust7")
    assert text == "Я здесь."
    (lead,) = sl.replay([e["payload"] for e in flow.store.events]).leads.values()
    assert lead.stage == sl.Stage.ENGAGED and not lead.notes
    run(op="inbound", arg="Сколько стоит?", reply="Я здесь.", user_id="cust7")
    assert len(flow.store.events) == 1  # same provider event -> no second fact


def test_router_routes_customer_free_text_to_sales_inbound() -> None:
    import inspect

    from core.policies.telegram import router

    assert '"op": "inbound"' in inspect.getsource(router.handle)


def test_managed_bot_wrapper_keeps_durable_keys_and_dedupes():
    import pytest

    from application.business_flows import sales_inbound as si
    kw = dict(route_business_id="b1", link_business_id="b1", managed_bot_id="mb7", telegram_user_id=42,
              update_id="9001", name="Аня", text="хочу записаться", ai_allowed=False)
    f = si.record_managed_bot_message([], **kw)
    assert f["dedupe_key"] == "managed-bot-message:mb7:9001" and f["surface"] == "managed_bot"
    assert "note" not in f
    assert si.record_managed_bot_message([f], **kw) is None
    for bad in (dict(link_business_id="b2"), dict(telegram_user_id=True), dict(update_id="x1")):
        with pytest.raises(ValueError):
            si.record_managed_bot_message([], **{**kw, **bad})


def test_record_message_rejects_non_bool_ai_flag():
    import pytest

    from application.business_flows import sales_inbound as si
    with pytest.raises(ValueError):
        si.record_message([], channel="vk", subject="1", name="", source_ref="s", event_id="e", text="hi", ai_allowed=1)
