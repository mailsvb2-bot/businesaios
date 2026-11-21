from __future__ import annotations

import re
import time

import pytest

from application.business_flows import partners
from runtime.handler_impl.domains.business_flow_ops import handle_partners


def test_partner_invitation_is_one_use_and_identity_bound():
    add = partners.parse_partner("Студия | wellness | 100 | opted_in | @studio")
    token = "a" * 43
    invited = partners.invitation(add["partner_id"], token, int(time.time()) + 1000)
    assert token not in repr(invited)
    events = [add, invited]
    bound = partners.claim_invitation(events, token, "12345", now=int(time.time()))
    assert bound["channel"] == "telegram"
    assert partners.bound_contacts(events + [bound]) == {add["partner_id"]: "12345"}
    assert partners.claim_invitation(events + [bound], token, "12345", now=int(time.time())) is None
    with pytest.raises(ValueError, match="already_claimed"):
        partners.claim_invitation(events + [bound], token, "54321", now=int(time.time()))
    with pytest.raises(ValueError):
        partners.claim_invitation(events, token, "not_numeric", now=int(time.time()))
    with pytest.raises(ValueError, match="expired"):
        partners.claim_invitation([add, partners.invitation(add["partner_id"], "b" * 43, 1)], "b" * 43, "12345", now=2)


def test_partner_inbound_and_outbound_are_bound_and_idempotent():
    add = partners.parse_partner("Студия | wellness | 100 | opted_in | @studio")
    token = "c" * 43
    bound = partners.claim_invitation([add, partners.invitation(add["partner_id"], token, 1000)],
                                      token, "12345", now=100)
    facts = [add, bound]
    with pytest.raises(PermissionError):
        partners.inbound_message(facts, "666", "Привет", "update-1")
    with pytest.raises(ValueError):
        partners.outbound_message([add], add["partner_id"], "Привет", "send-1")
    received = partners.inbound_message(facts, "12345", "Интересует размещение", "update-1")
    assert received["partner_id"] == add["partner_id"]
    assert partners.inbound_message(facts + [received], "12345", "Иное", "update-1") is None
    sent = partners.outbound_message(facts + [received], add["partner_id"], "Какие условия?", "send-1")
    assert [x["step"] for x in partners.conversation(facts + [received, sent], add["partner_id"])] == [
        "partner_message_in", "partner_message_out",
    ]


def test_partner_telegram_owner_to_partner_delivery_uses_canonical_effect(flow):
    flow.run(handle_partners, op="add", arg="Студия | wellness | 100 | opted_in | @studio")
    pid = partners.parse_partner("Студия | wellness | 100 | opted_in | @studio")["partner_id"]
    _, invite = flow.run(handle_partners, op="invite", arg=pid)
    token = re.search(r"/partner_join ([A-Za-z0-9_-]+)", invite).group(1)
    _, group = flow.run(handle_partners, op="join", arg=token, user_id="12345", source_chat_id="-100")
    assert "private_chat_required" in group
    _, reply = flow.run(handle_partners, op="join", arg=token, user_id="12345", source_chat_id="12345")
    assert "Контакт подтверждён" in reply
    _, accepted = flow.run(handle_partners, op="message_in", arg="Здравствуйте", user_id="12345",
                           source_message_key="update-19", source_chat_id="12345")
    assert "Сообщение принято" in accepted
    _, inbox = flow.run(handle_partners, op="inbox")
    assert "Здравствуйте" in inbox
    _, out = flow.run(handle_partners, op="send", arg=f"{pid} | Добрый день!")
    assert flow.effects.sent[-1]["user_id"] == "12345"
    assert flow.effects.sent[-1]["channel"] == "telegram"
    assert flow.effects.sent[-1]["text"] == "Добрый день!"
    assert flow.effects.sent[-1]["track_event_type"] == "partners@v1"
    assert flow.effects.sent[-1]["track_payload"]["step"] == "partner_message_out"
    _, stopped = flow.run(handle_partners, op="stop", user_id="12345", source_chat_id="12345")
    assert "Переписка отключена" in stopped
    _, blocked = flow.run(handle_partners, op="send", arg=f"{pid} | После отказа")
    assert "partner_not_bound" in blocked
    assert partners.bound_contacts([e["payload"] for e in flow.store.events]) == {}


def test_partner_routes_keep_single_decision_owner():
    from core.policies.telegram.routes.business_flow_routes import BUSINESS_FLOW_COMMANDS
    for cmd in ("/partner_invite", "/partner_join", "/partner_message",
                "/partner_send", "/partner_inbox", "/partner_stop"):
        assert BUSINESS_FLOW_COMMANDS[cmd][0] == "partners@v1"
    assert BUSINESS_FLOW_COMMANDS["/partner_join"][2] is False
    assert BUSINESS_FLOW_COMMANDS["/partner_send"][2] is True


def test_partner_route_enforces_owner_and_forwards_verified_chat():
    from types import SimpleNamespace

    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes

    state = SimpleNamespace(session={"channel": "telegram", "telegram_chat_id": "12345",
                                     "telegram_update_id": 302})
    def ctx(cmd, admin):
        return SimpleNamespace(state=state, callback_data="", callback_query_id=None,
                               cmd=cmd, args="Привет", is_admin=admin)
    assert handle_business_flow_routes(ctx("/partner_send", False), user_id="12345") is None
    message = handle_business_flow_routes(ctx("/partner_message", False), user_id="12345")
    assert message.action_type == "partners@v1" if hasattr(message, "action_type") else message is not None
    assert message.payload["source_chat_id"] == "12345"
    assert message.payload["source_message_key"] == "302"


def test_partner_messages_escape_html_only_at_telegram_delivery(flow):
    from html import escape

    flow.run(handle_partners, op="add", arg="Студия <test> | wellness | 100 | opted_in | @studio")
    pid = partners.parse_partner("Студия <test> | wellness | 100 | opted_in | @studio")["partner_id"]
    _, invite = flow.run(handle_partners, op="invite", arg=pid)
    assert "&lt;test&gt;" in invite
    token = re.search(r"/partner_join ([A-Za-z0-9_-]+)", invite).group(1)
    flow.run(handle_partners, op="join", arg=token, user_id="12345", source_chat_id="12345")
    incoming = "<proposal>Привет & готов обсудить</proposal>"
    flow.run(handle_partners, op="message_in", arg=incoming, user_id="12345",
             source_chat_id="12345", source_message_key="message-77")
    _, inbox = flow.run(handle_partners, op="inbox")
    assert escape(incoming) in inbox
    assert "&lt;test&gt;" in inbox
    outgoing = "<b>Условия & цена</b>"
    flow.run(handle_partners, op="send", arg=f"{pid} | {outgoing}")
    assert flow.effects.sent[-1]["text"] == escape(outgoing)
    assert flow.effects.sent[-1]["track_payload"]["text"] == outgoing
    assert incoming in [e["payload"]["text"] for e in flow.store.events
                        if e["payload"].get("step") == "partner_message_in"]


def test_customer_bot_partner_messages_keep_full_length_and_verified_source():
    from types import SimpleNamespace

    from core.actions.catalog import build_schema_registry
    from core.policies.telegram.routes.customer_bot_routes import handle_customer_bot

    message = "М" * 1200 + " <proposal>текст & условия</proposal>"
    session = {"source": "customer_bot_update", "channel": "telegram",
               "telegram_chat_id": "12345", "telegram_update_id": "933"}
    ctx = SimpleNamespace(cmd="/partner_message", args=message,
                          callback_query_id=None, state=SimpleNamespace(session=session))
    action = handle_customer_bot(ctx, user_id="12345")
    assert action.action == "partners@v1"
    assert action.payload["arg"] == message
    assert action.payload["source_chat_id"] == "12345"
    assert action.payload["source_message_key"] == "933"
    build_schema_registry().validate(action.action, {"tenant_id": "t1", **action.payload})
    ctx.args = "X" * 2001
    denied = handle_customer_bot(ctx, user_id="12345")
    assert denied.action != "partners@v1"
    assert "Не сохранено" in denied.payload["text"]
