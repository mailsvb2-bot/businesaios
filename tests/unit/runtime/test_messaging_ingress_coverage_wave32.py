from __future__ import annotations

from inspect import signature

import runtime.messaging_ingress as ingress
from runtime.messaging.channel_types import ALL_CHANNELS


def test_supported_channel_catalog_delegates_to_runtime_without_ingress_only_exceptions() -> None:
    assert ingress.INGRESS_ONLY_MESSAGING_CHANNELS == ()
    assert ingress.SUPPORTED_MESSAGING_CHANNELS == ALL_CHANNELS
    assert ingress.normalize_messaging_channel("tg") == "telegram"
    assert ingress.normalize_messaging_channel("telegram bot") == "telegram"
    assert ingress.normalize_messaging_channel("wa") == "whatsapp"
    assert ingress.normalize_messaging_channel("whats-app") == "whatsapp"
    assert ingress.normalize_messaging_channel("webchat") == "web_chat"
    assert ingress.normalize_messaging_channel("instagram dm") == "instagram"
    assert ingress.normalize_messaging_channel("vkontakte") == "vk"
    assert ingress.normalize_messaging_channel("vk bot") == "vk"
    assert ingress.normalize_messaging_channel("mail") == "email"
    assert ingress.normalize_messaging_channel("e mail") == "email"
    assert ingress.normalize_messaging_channel("MAX") == "max"
    assert ingress.normalize_messaging_channel("") == "unknown"
    assert ingress.normalize_messaging_channel("future-channel") == "future_channel"


def test_command_split_preserves_plain_text_command_and_arguments() -> None:
    assert ingress.split_command(None) == ("", "")
    assert ingress.split_command(" hello ") == ("", "hello")
    assert ingress.split_command("/start") == ("/start", "")
    assert ingress.split_command(" /price   premium ") == ("/price", "premium")


def test_generic_payload_adapter_preserves_zero_ids_and_field_priority() -> None:
    event = ingress.payload_to_messaging_event(
        "facebook_messenger",
        {
            "entry": [{"messaging": [{
                "sender": {"id": "42"},
                "message": {"text": "/buy plan-pro"},
            }]}],
            "timestamp_ms": "bad",
            "created_at_ms": "1700",
            "update_id": 0,
            "event_id": "later-id",
        },
        tenant_id="tenant-1",
        product_name="Product",
        timezone="UTC",
    )
    assert event.channel == "messenger"
    assert event.user_id == "42"
    assert event.chat_id == "42"
    assert event.text == "/buy plan-pro"
    assert event.command == "/buy"
    assert event.args == "plan-pro"
    assert event.timestamp_ms == 1700
    assert event.update_id == 0
    assert event.tenant_id == "tenant-1"
    assert event.product_name == "Product"
    assert event.timezone == "UTC"
    assert event.raw["event_id"] == "later-id"

    fallback = ingress.payload_to_messaging_event(
        "future-channel",
        {},
        tenant_id="tenant-2",
    )
    assert fallback.channel == "future_channel"
    assert fallback.user_id == ""
    assert fallback.chat_id == ""
    assert fallback.timestamp_ms == 0
    assert str(fallback.update_id).startswith("synthetic-future_channel-")


def test_every_concrete_provider_adapter_uses_the_provider_sender_contract() -> None:
    fixtures = {
        "whatsapp": ({"entry": [{"changes": [{"value": {"messages": [{
            "from": "user", "text": {"body": "hello"}, "id": "id-1",
        }]}}]}]}, "user"),
        "vk": ({"object": {"message": {
            "user_id": 7, "peer_id": 70, "text": "hello", "id": 1,
        }}}, "70"),
        "max": ({"message": {
            "sender": {"user_id": "user"},
            "recipient": {"chat_id": "thread"},
            "body": {"text": "hello", "mid": "id-1"},
        }}, "thread"),
        "slack": ({"event": {
            "user": "user", "channel": "thread", "text": "hello", "client_msg_id": "id-1",
        }}, "thread"),
        "discord": ({"author": {"id": "user"}, "channel_id": "thread", "content": "hello", "id": "id-1"}, "thread"),
        "viber": ({"sender": {"id": "user"}, "chat_id": "thread",
                   "message": {"text": "hello"}, "message_token": "id-1"}, "thread"),
        "sms": ({"from": "user", "to": "thread", "body": "hello", "message_id": "id-1"}, "thread"),
        "email": ({"from": "user@example.test", "to": "inbox@example.test",
                   "text": "hello", "message_id": "id-1"}, "inbox@example.test"),
        "instagram": ({"entry": [{"messaging": [{
            "sender": {"id": "user"}, "message": {"text": "hello", "mid": "id-1"},
        }]}]}, "user"),
        "messenger": ({"entry": [{"messaging": [{
            "sender": {"id": "user"}, "message": {"text": "hello", "mid": "id-1"},
        }]}]}, "user"),
        "line": ({"events": [{
            "source": {"userId": "user", "groupId": "thread"},
            "message": {"text": "hello", "id": "id-1"},
        }]}, "thread"),
        "wechat": ({"FromUserName": "user", "ToUserName": "thread",
                    "Content": "hello", "MsgId": "id-1"}, "thread"),
        "kakaotalk": ({"userRequest": {
            "user": {"id": "user", "properties": {"plusfriendUserKey": "thread"}},
            "utterance": "hello", "block": {"id": "id-1"},
        }}, "thread"),
    }
    wrappers = {
        "whatsapp": ingress.whatsapp_payload_to_messaging_event,
        "vk": ingress.vk_payload_to_messaging_event,
        "max": ingress.max_payload_to_messaging_event,
        "slack": ingress.slack_payload_to_messaging_event,
        "discord": ingress.discord_payload_to_messaging_event,
        "viber": ingress.viber_payload_to_messaging_event,
        "sms": ingress.sms_payload_to_messaging_event,
        "email": ingress.email_payload_to_messaging_event,
        "instagram": ingress.instagram_payload_to_messaging_event,
        "messenger": ingress.messenger_payload_to_messaging_event,
        "line": ingress.line_payload_to_messaging_event,
        "wechat": ingress.wechat_payload_to_messaging_event,
        "kakaotalk": ingress.kakaotalk_payload_to_messaging_event,
    }
    for expected_channel, adapter in wrappers.items():
        assert adapter.__name__ == f"{expected_channel.replace('_', '')}_payload_to_messaging_event"
        assert tuple(signature(adapter).parameters) == ("payload", "tenant_id", "product_name", "timezone")
        payload, expected_chat = fixtures[expected_channel]
        event = adapter(payload, tenant_id="tenant", product_name="Product", timezone="UTC")
        assert event.channel == expected_channel
        assert event.user_id == ("7" if expected_channel == "vk" else "user")
        assert event.chat_id == expected_chat
        assert event.text == "hello"
        assert event.update_id == "id-1"
        assert event.product_name == "Product"
        assert event.timezone == "UTC"

    for expected_channel, adapter in {
        "web_chat": ingress.webchat_payload_to_messaging_event,
        "api": ingress.api_payload_to_messaging_event,
    }.items():
        event = adapter(
            {"user_id": "user", "chat_id": "thread", "text": "hello", "message_id": "id-1"},
            tenant_id="tenant", product_name="Product", timezone="UTC",
        )
        assert event.channel == expected_channel
        assert event.user_id == "user"
        assert event.chat_id == "thread"
        assert event.text == "hello"
        assert event.update_id == "id-1"


def test_provider_adapters_never_promote_generic_author_or_thread_to_verified_sender() -> None:
    wrappers = (
        ingress.whatsapp_payload_to_messaging_event,
        ingress.vk_payload_to_messaging_event,
        ingress.max_payload_to_messaging_event,
        ingress.slack_payload_to_messaging_event,
        ingress.discord_payload_to_messaging_event,
        ingress.viber_payload_to_messaging_event,
        ingress.sms_payload_to_messaging_event,
        ingress.email_payload_to_messaging_event,
        ingress.instagram_payload_to_messaging_event,
        ingress.messenger_payload_to_messaging_event,
        ingress.line_payload_to_messaging_event,
        ingress.wechat_payload_to_messaging_event,
        ingress.kakaotalk_payload_to_messaging_event,
    )
    for adapter in wrappers:
        event = adapter(
            {"author_id": "spoofed-user", "thread_id": "recipient-only", "content": "hello"},
            tenant_id="tenant",
        )
        assert event.user_id == ""
        assert event.chat_id == "recipient-only"
        assert event.text == "hello"


def test_world_state_adapter_is_normalization_only_and_preserves_decision_coordinates() -> None:
    event = ingress.MessagingIngressEvent(
        channel="webchat",
        user_id="",
        chat_id="chat-1",
        text="/help billing",
        tenant_id="",
        timestamp_ms=7,
        update_id=0,
        product_name="",
        timezone="",
    )
    state = ingress.messaging_event_to_world_state(event)
    assert state.schema_version == 1
    assert state.tenant_id == "default"
    assert state.user_id == ""
    assert state.user == {
        "id": "",
        "messaging_user_id": "",
        "messaging_chat_id": "chat-1",
        "messaging_channel": "web_chat",
        "timezone": "Europe/Amsterdam",
    }
    assert state.session["command"] == "/help"
    assert state.session["args"] == "billing"
    assert state.session["messaging_update_id"] == 0
    assert state.product == {"name": "BusinesAIOS", "channel": "web_chat"}
    assert state.timestamp_ms == 7
    assert state.meta == {
        "source": "messaging",
        "channel": "web_chat",
        "supported_channel": True,
    }

    explicit = ingress.messaging_event_to_world_state(
        ingress.MessagingIngressEvent(
            channel="future",
            user_id="user",
            text="ignored",
            command="/explicit",
            args="argument",
        )
    )
    assert explicit.session["command"] == "/explicit"
    assert explicit.session["args"] == "argument"
    assert explicit.meta["supported_channel"] is False

    anonymous = ingress.messaging_event_to_world_state(ingress.MessagingIngressEvent(channel="sms", user_id=""))
    assert anonymous.user_id == ""


def test_telegram_message_update_preserves_sender_chat_command_and_seconds_to_ms() -> None:
    event = ingress.telegram_update_to_messaging_event(
        {
            "update_id": 0,
            "message": {
                "date": "12",
                "text": "/start now",
                "chat": {"id": -100},
                "from": {"id": 77},
            },
        },
        tenant_id="tenant",
    )
    assert event.user_id == "77"
    assert event.chat_id == "-100"
    assert event.command == "/start"
    assert event.args == "now"
    assert event.timestamp_ms == 12_000
    assert event.update_id == 0


def test_telegram_callback_and_message_variants_are_fail_closed() -> None:
    callback = ingress.telegram_update_to_messaging_event(
        {
            "update_id": 9,
            "callback_query": {
                "data": " callback-data ",
                "from": {"id": 88},
                "message": {
                    "date": "invalid",
                    "caption": "caption",
                    "chat": {"id": 99},
                },
            },
        },
        tenant_id="tenant",
    )
    assert callback.text == "callback-data"
    assert callback.user_id == "88"
    assert callback.chat_id == "99"
    assert callback.timestamp_ms == 0

    no_data = ingress.telegram_update_to_messaging_event(
        {
            "callback_query": {
                "data": "",
                "message": {"text": "message text", "chat": {"id": "chat"}},
            }
        },
        tenant_id="tenant",
    )
    assert no_data.text == "message text"
    assert no_data.user_id == ""

    edited = ingress.telegram_update_to_messaging_event(
        {"edited_message": {"caption": "edited", "from": {"id": "sender"}}},
        tenant_id="tenant",
    )
    assert edited.text == "edited"
    assert edited.user_id == "sender"
    assert edited.chat_id == ""

    empty = ingress.telegram_update_to_messaging_event({}, tenant_id="tenant")
    assert empty.user_id == ""
    assert empty.text == ""
    assert empty.raw == {}


def test_ingress_has_no_private_parallel_extractors_and_decoder_fails_closed() -> None:
    for retired in (
        "_first_text",
        "_first_value",
        "_first_int",
        "_telegram_message",
        "_telegram_text",
        "_telegram_chat_id",
        "_telegram_sender_id",
    ):
        assert not hasattr(ingress, retired)

    event = ingress.payload_to_messaging_event(
        "telegram",
        {
            "message": "not-a-map",
            "callback_query": {"message": "not-a-map"},
            "timestamp_ms": "invalid",
        },
        tenant_id="tenant",
    )
    assert event.channel == "telegram"
    assert event.user_id == ""
    assert event.chat_id == ""
    assert event.text == ""
    assert event.timestamp_ms == 0
    assert str(event.update_id).startswith("synthetic-telegram-")
