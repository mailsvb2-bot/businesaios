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


def test_inbound_mapper_keeps_command_and_callback_without_untrusted_business_scope():
    state = map_inbound_to_world_state(InboundMessage(
        tenant_id="t1", user_id="u1", channel="vk", text="/START@BotName ref_abc",
        transport_message_id="m1", metadata={"chat_id": "77", "business_id": "biz-9"}))
    assert state.session["command"] == "/start"
    assert state.session["args"] == "ref_abc"
    assert "business_id" not in state.session
    assert state.session["is_callback"] is False
    callback = map_inbound_to_world_state(InboundMessage(
        tenant_id="t1", user_id="u1", channel="max", text="cpm:customers:42",
        transport_message_id="m2", metadata={"chat_id": "77"}))
    assert callback.session["is_callback"] is True
    assert callback.session["callback_data"] == "cpm:customers:42"
    assert "business_id" not in callback.session



def test_signed_inbound_foreign_business_metadata_never_reaches_decision_or_executor():
    from types import SimpleNamespace
    from runtime.business_autonomy.provider_webhook_inbound_processor import ProviderWebhookInboundProcessor

    class CapturingCore:
        state = None

        def issue(self, state):
            self.state = state
            return SimpleNamespace(decision=SimpleNamespace(
                decision_id="decision-1", correlation_id="update-1"))

    core = CapturingCore()
    handoff = {"inbound_message": {
        "tenant_id": "tenant-a", "channel": "telegram", "user_id": "user-1",
        "text": "/start", "correlation_id": "update-1",
        "metadata": {"tenant_id": "tenant-b", "business_id": "foreign-business",
                     "chat_id": "user-1", "verified": True},
    }}
    result = ProviderWebhookInboundProcessor(decision_core=core).process(handoff=handoff)
    assert result["accepted"] is True
    assert core.state.tenant_id == "tenant-a"
    assert core.state.session["chat_id"] == "user-1"
    assert "business_id" not in core.state.session
    assert "tenant_id" not in core.state.session
    assert "foreign-business" not in repr(core.state)
    assert "execution" not in result
