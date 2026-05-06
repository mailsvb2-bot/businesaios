from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging.inbound_message import InboundMessage
from runtime.messaging.outbound_message import OutboundMessage


def test_channel_preference_normalizes_and_keeps_one_primary():
    pref = ChannelPreference(primary="WhatsApp", enabled=("telegram", "whatsapp", "telegram"), verified=("whatsapp",))
    assert pref.primary == "whatsapp"
    assert pref.enabled == ("whatsapp", "telegram")
    assert pref.verified == ("whatsapp",)


def test_delivery_key_is_channel_aware():
    a = OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="42", channel="telegram", text="hi")
    b = OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="42", channel="whatsapp", text="hi")
    assert a.delivery_key != b.delivery_key


def test_inbound_message_normalizes_aliases():
    msg = InboundMessage(tenant_id="t1", user_id="u1", channel="instagram_dm", text="hello", external_user_ref="ext-1")
    assert msg.channel == "instagram"
