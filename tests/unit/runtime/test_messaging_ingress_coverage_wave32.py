from __future__ import annotations

import runtime.messaging_ingress as ingress
from runtime.messaging.channel_types import ALL_CHANNELS


def test_supported_channel_catalog_delegates_to_runtime_and_preserves_ingress_only_channels() -> None:
    assert ingress.INGRESS_ONLY_MESSAGING_CHANNELS == ("vk", "max")
    assert ingress.SUPPORTED_MESSAGING_CHANNELS == (*ALL_CHANNELS, "vk", "max")
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
            "text": None,
            "message": "/buy plan-pro",
            "user_id": None,
            "from_id": 42,
            "chat_id": None,
            "conversation_id": "conversation-7",
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
    assert event.chat_id == "conversation-7"
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
    assert fallback.user_id == "future_channel_user"
    assert fallback.chat_id == ""
    assert fallback.timestamp_ms == 0
    assert fallback.update_id is None


def test_every_concrete_provider_adapter_uses_the_shared_payload_contract() -> None:
    wrappers = {
        "whatsapp": ingress.whatsapp_payload_to_messaging_event,
        "vk": ingress.vk_payload_to_messaging_event,
        "max": ingress.max_payload_to_messaging_event,
        "slack": ingress.slack_payload_to_messaging_event,
        "discord": ingress.discord_payload_to_messaging_event,
        "viber": ingress.viber_payload_to_messaging_event,
        "sms": ingress.sms_payload_to_messaging_event,
        "email": ingress.email_payload_to_messaging_event,
        "web_chat": ingress.webchat_payload_to_messaging_event,
        "instagram": ingress.instagram_payload_to_messaging_event,
        "messenger": ingress.messenger_payload_to_messaging_event,
        "line": ingress.line_payload_to_messaging_event,
        "wechat": ingress.wechat_payload_to_messaging_event,
        "kakaotalk": ingress.kakaotalk_payload_to_messaging_event,
        "api": ingress.api_payload_to_messaging_event,
    }
    for expected_channel, adapter in wrappers.items():
        event = adapter(
            {"author_id": "user", "thread_id": "thread", "content": "hello", "id": "id-1"},
            tenant_id="tenant",
            product_name="Product",
            timezone="UTC",
        )
        assert event.channel == expected_channel
        assert event.user_id == "user"
        assert event.chat_id == "thread"
        assert event.text == "hello"
        assert event.update_id == "id-1"
        assert event.product_name == "Product"
        assert event.timezone == "UTC"


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
    assert state.user_id == "chat-1"
    assert state.user == {
        "id": "chat-1",
        "messaging_user_id": "chat-1",
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
    assert anonymous.user_id == "messaging_user"


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
    assert no_data.user_id == "chat"

    edited = ingress.telegram_update_to_messaging_event(
        {"edited_message": {"caption": "edited", "from": {"id": "sender"}}},
        tenant_id="tenant",
    )
    assert edited.text == "edited"
    assert edited.user_id == "sender"
    assert edited.chat_id == ""

    empty = ingress.telegram_update_to_messaging_event({}, tenant_id="tenant")
    assert empty.user_id == "telegram_user"
    assert empty.text == ""
    assert empty.raw == {}


def test_private_extractors_cover_absent_non_mapping_and_invalid_values() -> None:
    assert ingress._first_text({"a": None, "b": 5}, "a", "b") == "5"
    assert ingress._first_text({}, "missing") == ""
    assert ingress._first_value({"a": None, "b": 0}, "a", "b") == 0
    assert ingress._first_value({}, "missing") is None
    assert ingress._first_int({"a": None, "b": "bad", "c": 4}, "a", "b", "c") == 4
    assert ingress._first_int({}, "missing") == 0

    assert ingress._telegram_message({"message": "not-a-map"}) == {}
    assert ingress._telegram_message({"callback_query": "not-a-map"}) == {}
    assert ingress._telegram_message({"callback_query": {"message": "not-a-map"}}) == {}
    assert ingress._telegram_text({"callback_query": "not-a-map"}, {"caption": "cap"}) == "cap"
    assert ingress._telegram_chat_id({"chat": "not-a-map"}) == ""
    assert ingress._telegram_chat_id({"chat": {"id": None}}) == ""
    assert ingress._telegram_sender_id({"callback_query": {"from": "not-a-map"}}, {}) == ""
    assert ingress._telegram_sender_id({}, {"from": "not-a-map"}) == ""
    assert ingress._telegram_sender_id({}, {"from": {"id": None}}) == ""
