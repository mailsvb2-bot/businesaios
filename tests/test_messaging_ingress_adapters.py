from __future__ import annotations

from kernel.world_state import WorldStateV1
from runtime.messaging_ingress import (
    MessagingIngressEvent,
    discord_payload_to_messaging_event,
    email_payload_to_messaging_event,
    max_payload_to_messaging_event,
    messaging_event_to_world_state,
    slack_payload_to_messaging_event,
    sms_payload_to_messaging_event,
    viber_payload_to_messaging_event,
    vk_payload_to_messaging_event,
    webchat_payload_to_messaging_event,
    whatsapp_payload_to_messaging_event,
)


def test_concrete_messaging_adapters_return_ingress_events():
    adapters = {
        "whatsapp": whatsapp_payload_to_messaging_event,
        "vk": vk_payload_to_messaging_event,
        "max": max_payload_to_messaging_event,
        "slack": slack_payload_to_messaging_event,
        "discord": discord_payload_to_messaging_event,
        "viber": viber_payload_to_messaging_event,
        "sms": sms_payload_to_messaging_event,
        "email": email_payload_to_messaging_event,
        "webchat": webchat_payload_to_messaging_event,
    }

    for channel, adapter in adapters.items():
        event = adapter(
            {
                "user_id": "u1",
                "chat_id": "c1",
                "text": "/start demo",
                "message_id": "m1",
                "timestamp_ms": 1,
            },
            tenant_id="tenant_a",
        )
        assert isinstance(event, MessagingIngressEvent)
        assert event.channel == channel
        assert event.user_id == "u1"
        assert event.chat_id == "c1"
        assert event.command == "/start"
        assert event.args == "demo"

        state = messaging_event_to_world_state(event)
        assert isinstance(state, WorldStateV1)
        assert state.tenant_id == "tenant_a"
        assert state.session["source"] == "messaging"
        assert state.session["channel"] == channel
        assert state.session["messaging_update_id"] == "m1"
