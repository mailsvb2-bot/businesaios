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
