from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.dispatcher import MultiChannelDispatcher
from runtime.messaging.outbound_message import OutboundMessage


class _Adapter:
    def __init__(self, name: str):
        self.name = name
        self.items = []

    def send(self, msg):
        self.items.append(msg)
        return DeliveryResult(ok=True, channel=msg.channel, mode="test", external_id=f"{self.name}:{msg.user_id}")


def test_dispatcher_routes_by_channel():
    wa = _Adapter("wa")
    tg = _Adapter("tg")
    disp = MultiChannelDispatcher(adapters={"whatsapp": wa, "telegram": tg})
    out = disp.send(OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="user-1", channel="whatsapp", text="hello"))
    assert out.ok is True
    assert out.channel == "whatsapp"
    assert out.external_id == "wa:user-1"
    assert len(wa.items) == 1
    assert len(tg.items) == 0
