import pytest

from application.business_flows import partner_outreach as po
from application.business_flows import partners as pt

ADD = pt.parse_partner("Йога-студия | йога | 500 | opted_in | @yoga")
PUB = pt.parse_partner("Кафе | еда | 100 | public | hi@cafe.ru")


def test_send_connections():
    conns = [
        {
            "id": "b",
            "platform": "telegram",
            "status": "active",
            "type": "telegram_managed_bot",
            "external_account_id": "mybot",
        },
        {"id": "a", "platform": "telegram", "status": "paused", "type": "telegram_shared_bot"},
        {"id": "e", "platform": "email", "status": "active", "type": "email_smtp"},
    ]
    assert [c.label for c in po.send_connections(conns)] == ["Telegram · mybot"]
    assert po.send_connections(conns, "email")[0].label == "Email · отправитель"
    with pytest.raises(ValueError):
        po.send_connections(conns, "sms")


def test_authorize_and_queue_gates():
    ps = pt.replay([ADD, PUB])
    yoga, cafe = ps[ADD["partner_id"]], ps[PUB["partner_id"]]
    with pytest.raises(PermissionError):
        po.authorize_telegram_contact(yoga, "new", chat_id="123", basis="public")
    with pytest.raises(ValueError):
        po.authorize_telegram_contact(yoga, "new", chat_id="abc", basis="opted_in")
    with pytest.raises(PermissionError):
        po.authorize_telegram_contact(yoga, "declined", chat_id="123", basis="opted_in")
    auth = po.authorize_telegram_contact(yoga, "prepared", chat_id="123", basis="opted_in")
    q = po.queue_outreach(yoga, "prepared", contact=po.contacts([auth])[yoga.partner_id], connection_id="b")
    assert q["channel"] == "telegram" and q["to"] == "123" and q["step"] == "partner_outreach_queued"
    with pytest.raises(PermissionError):
        po.queue_outreach(cafe, "prepared", contact=None, connection_id="e")
    assert (
        po.queue_outreach(cafe, "prepared", contact=None, connection_id="e", explicit_owner_approval=True)["to"]
        == "hi@cafe.ru"
    )


def test_reply_matching_idempotent():
    pid = ADD["partner_id"]
    facts = [
        ADD,
        {"step": "partner_status", "partner_id": pid, "status": "contacted"},
        {"step": "partner_outreach_sent", "partner_id": pid, "connection_id": "b", "channel": "telegram", "to": "123"},
    ]
    assert (
        po.record_reply_if_expected(
            facts, connection_id="b", external_subject="999", provider_event_key="k", reply_text="x", at="t"
        )
        == []
    )
    out = po.record_reply_if_expected(
        facts,
        connection_id="b",
        external_subject="123",
        provider_event_key="k",
        reply_text="Да\x00!",
        at="2026-10-23T10:00",
    )
    assert out[0]["reply_text"] == "Да !" and out[1]["status"] == "replied"
    facts += out
    assert (
        po.record_reply_if_expected(
            facts, connection_id="b", external_subject="123", provider_event_key="k", reply_text="x", at="t"
        )
        == []
    )
    assert po.replies(facts, pid)[0].reply_text == "Да !"
    assert po.stats(facts) == {"candidates": 1, "replied": 1, "queued": 0, "replies": 1}
