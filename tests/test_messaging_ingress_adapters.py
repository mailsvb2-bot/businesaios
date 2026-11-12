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
        "web_chat": webchat_payload_to_messaging_event,
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


def test_start_command_canonicalised_across_bot_mentions_and_case():
    from runtime.messaging_ingress import split_command

    assert split_command("/start@my_bot ref_1") == ("/start", "ref_1")
    assert split_command("/START") == ("/start", "")
    assert split_command("привет") == ("", "привет")


def test_vk_start_button_json_payload_decodes_to_start_command():
    from runtime.messaging.provider_inbound_decoder import decode_provider_inbound

    raw = {"type": "message_new", "object": {"message": {
        "from_id": 5, "peer_id": 5, "id": 9, "text": "Начать",
        "payload": '{"command":"start"}'}}}
    decoded = decode_provider_inbound(channel="vk", payload=raw)
    assert decoded["text"] == "/start"
    assert raw["object"]["message"]["payload"] == '{"command":"start"}'
    raw["object"]["message"]["payload"] = '{"callback_data":"menu:main"}'
    assert decode_provider_inbound(channel="vk", payload=raw)["text"] == "menu:main"


def test_max_bot_started_decodes_to_start_with_payload():
    from runtime.messaging.provider_inbound_decoder import decode_provider_inbound

    raw = {"update_type": "bot_started", "timestamp": 1, "chat_id": 77,
           "user": {"user_id": 42, "name": "A"}, "payload": "ref_abc"}
    decoded = decode_provider_inbound(channel="max", payload=raw)
    assert decoded["text"] == "/start ref_abc"
    assert decoded["user_id"] == "42" and decoded["chat_id"] == "77"


def _provider_world_state(channel: str, text: str, metadata: dict | None = None):
    from runtime.messaging.inbound_message import InboundMessage
    from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state
    return map_inbound_to_world_state(InboundMessage(
        tenant_id="tenant-a", user_id="77", channel=channel, text=text,
        transport_message_id="evt-1",
        metadata={"chat_id": "77", "business_id": "biz-1", **dict(metadata or {})},
    ))


def test_webhook_start_routes_to_clientplatform_without_telegram():
    from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
    from runtime.messaging.provider_inbound_decoder import decode_provider_inbound
    vk = decode_provider_inbound(channel="vk", payload={"type": "message_new", "object": {
        "message": {"from_id": 77, "peer_id": 77, "id": 9, "text": "Начать",
                    "payload": '{"command":"start"}'}}})
    max_started = decode_provider_inbound(channel="max", payload={
        "update_type": "bot_started", "timestamp": 1, "chat_id": 77,
        "user": {"user_id": 77, "name": "A"}, "payload": ""})
    for channel, decoded in (("vk", vk), ("max", max_started),
                             ("whatsapp", {"text": "/START@Bot"})):
        state = _provider_world_state(channel, str(decoded["text"]))
        assert state.session["command"] == "/start"
        outcome = UnifiedTelegramPolicyV3().propose(state)
        assert outcome.action == "send_message@v1"
        assert "ClientPlatform" in outcome.payload["text"]


def test_webhook_folded_callback_reaches_main_menu():
    from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
    state = _provider_world_state("vk", "menu:main")
    assert state.session["is_callback"] is True
    assert state.session["callback_data"] == "menu:main"
    outcome = UnifiedTelegramPolicyV3().propose(state)
    assert outcome.action == "send_message@v1"
    assert "ClientPlatform" in outcome.payload["text"]
