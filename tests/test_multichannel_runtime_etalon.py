from interfaces.messaging_runtime.contracts import InboundMessage
from interfaces.messaging_runtime.registry import ChannelRegistry
from interfaces.messaging_runtime.routing import route_message


def test_contract_and_registry_runtime_etalon():
    msg = InboundMessage(channel="sms", user_id="1", payload={})
    registry = ChannelRegistry()
    registry.register("sms", object())
    assert route_message(msg) == "sms"
    assert registry.get("sms") is not None
