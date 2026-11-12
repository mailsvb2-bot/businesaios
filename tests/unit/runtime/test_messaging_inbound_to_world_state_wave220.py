from runtime.messaging.inbound_message import InboundMessage
from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state


def test_inbound_message_maps_to_world_state_message_input():
    out = map_inbound_to_world_state(
        InboundMessage(
            tenant_id="t1",
            user_id="u1",
            channel="telegram",
            text="hello",
            external_user_ref="u1",
            transport_message_id="m1",
            correlation_id="c1",
        )
    )
    assert out.tenant_id == "t1"
    assert out.user_id == "u1"
    assert out.channel == "telegram"
    assert out.message_text == "hello"
    assert out.transport_message_id == "m1"
    assert out.session["text"] == "hello"
    assert out.session["command"] == ""


def test_inbound_mapper_keeps_command_and_callback_with_business_scope():
    state = map_inbound_to_world_state(InboundMessage(
        tenant_id="t1", user_id="u1", channel="vk", text="/START@BotName ref_abc",
        transport_message_id="m1", metadata={"chat_id": "77", "business_id": "biz-9"}))
    assert state.session["command"] == "/start"
    assert state.session["args"] == "ref_abc"
    assert state.session["business_id"] == "biz-9"
    assert state.session["is_callback"] is False
    callback = map_inbound_to_world_state(InboundMessage(
        tenant_id="t1", user_id="u1", channel="max", text="cpm:customers:42",
        transport_message_id="m2", metadata={"chat_id": "77"}))
    assert callback.session["is_callback"] is True
    assert callback.session["callback_data"] == "cpm:customers:42"
    assert "business_id" not in callback.session

