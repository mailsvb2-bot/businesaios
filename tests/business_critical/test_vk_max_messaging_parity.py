from __future__ import annotations

import json

import pytest

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging.provider_inbound_decoder import decode_provider_inbound


def _vk_normalize(reply_markup: dict) -> dict:
    return ProviderPayloadNormalizers().normalize_outbound(
        provider=provider_map()["vk_messaging"],
        operation="message_send",
        payload={"user_id": "42", "text": "choose", "reply_markup": reply_markup},
    )


def test_vk_canonical_inline_keyboard_translates_without_second_ui_model() -> None:
    normalized = _vk_normalize(
        {"inline_keyboard": [[{"text": "Open", "callback_data": "menu:open"}], [{"text": "Site", "url": "https://example.com"}]]}
    )
    keyboard = json.loads(normalized["keyboard"])
    assert keyboard["inline"] is True
    assert keyboard["buttons"][0][0]["action"] == {
        "type": "callback",
        "label": "Open",
        "payload": '{"callback_data":"menu:open"}',
    }
    assert keyboard["buttons"][1][0]["action"] == {
        "type": "open_link",
        "label": "Site",
        "link": "https://example.com",
    }
    assert provider_map()["vk_messaging"].messaging_capabilities["buttons"] is True


def test_vk_large_callback_keyboard_preserves_actions_in_provider_valid_rows() -> None:
    buttons = [{"text": f"B{index}", "callback_data": f"cmd:{index}"} for index in range(1, 13)]
    keyboard = json.loads(_vk_normalize({"inline_keyboard": [[item] for item in buttons]})["keyboard"])
    assert keyboard["inline"] is False
    assert len(keyboard["buttons"]) == 6
    assert all(1 <= len(row) <= 5 for row in keyboard["buttons"])
    actions = [button["action"] for row in keyboard["buttons"] for button in row]
    assert [action["label"] for action in actions] == [f"B{index}" for index in range(1, 13)]
    assert all(action["type"] == "text" for action in actions)
    assert [json.loads(action["payload"])["callback_data"] for action in actions] == [
        f"cmd:{index}" for index in range(1, 13)
    ]


def test_vk_keyboard_refuses_silent_functionality_loss_beyond_provider_capacity() -> None:
    buttons = [{"text": f"B{index}", "callback_data": f"cmd:{index}"} for index in range(31)]
    with pytest.raises(ValueError, match="capacity"):
        _vk_normalize({"inline_keyboard": [[item] for item in buttons]})


def test_vk_message_event_round_trips_callback_into_canonical_inbound() -> None:
    payload = {
        "type": "message_event",
        "group_id": 123,
        "object": {
            "event_id": "evt-1",
            "user_id": 700001,
            "peer_id": 700001,
            "payload": {"callback_data": "menu:open"},
        },
    }
    decoded = decode_provider_inbound(channel="vk", payload=payload)
    assert (decoded["user_id"], decoded["chat_id"], decoded["text"], decoded["message_id"]) == (
        "700001", "700001", "menu:open", "evt-1"
    )
    route = ProviderWebhookRouteRegistry().extract(
        provider_map()["vk_messaging"], {}, json.dumps(payload).encode()
    )
    assert route["event_key"] == "evt-1"
    assert route["resource_id"] == "evt-1"
    assert route["messaging_ingress"]["text"] == "menu:open"
    assert route["messaging_ingress"]["user_id"] == "700001"


def test_vk_text_keyboard_payload_round_trips_callback_data() -> None:
    decoded = decode_provider_inbound(
        channel="vk",
        payload={
            "type": "message_new",
            "event_id": "evt-2",
            "object": {
                "message": {
                    "from_id": 700001,
                    "peer_id": 700001,
                    "text": "Open",
                    "payload": {"callback_data": "menu:open"},
                }
            },
        },
    )
    assert decoded["text"] == "menu:open"


def test_max_callback_uses_provider_callback_id_as_replay_identity() -> None:
    payload = {
        "update_type": "message_callback",
        "timestamp": 1787259600000,
        "user": {"user_id": 778899},
        "callback": {"callback_id": "max-callback-1", "payload": "one"},
    }
    route = ProviderWebhookRouteRegistry().extract(
        provider_map()["max_messaging"], {}, json.dumps(payload).encode()
    )
    assert route["event_key"] == "max-callback-1"
    assert route["resource_id"] == "max-callback-1"
    assert route["messaging_ingress"]["text"] == "one"
    assert route["messaging_ingress"]["user_id"] == "778899"


def test_native_vk_adapter_carries_canonical_markup_into_approved_provider_subject() -> None:
    class _Registry:
        def get(self, key: str):
            return provider_map()[key]

    class _Service:
        provider_registry = _Registry()

        def __init__(self) -> None:
            self.calls: list[dict] = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "dispatch": {
                    "queued": False,
                    "status": "rejected_provider_write_guard",
                    "job_id": "",
                    "metadata": {
                        "provider_write_guard": {
                            "reason": "approval_required",
                            "metadata": {
                                "approval": {
                                    "approval_id": "ap-vk-1",
                                    "approval_required": True,
                                    "reason": "approval_submitted_awaiting_operator",
                                }
                            },
                        }
                    },
                },
                "result": None,
            }

    service = _Service()
    adapter = _NativeProviderQueueAdapter("vk", service_factory=lambda: service)
    message = OutboundMessage(
        decision_id="dec-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        business_id="biz-a",
        user_id="42",
        channel="vk",
        text="hello",
        reply_markup={"inline_keyboard": [[{"text": "Open", "callback_data": "menu:open"}]]},
        track_payload={"_provider_native": {"business_id": "biz-a"}},
    )
    result = adapter.send(message)
    assert result.mode == "approval_required"
    sent = service.calls[0]
    assert sent["provider_key"] == "vk_messaging"
    assert sent["payload"]["peer_id"] == "42"
    keyboard = json.loads(sent["payload"]["keyboard"])
    assert keyboard["buttons"][0][0]["action"]["payload"] == '{"callback_data":"menu:open"}'
    assert sent["payload"]["_approval"] == {
        "decision_id": "dec-1",
        "execution_id": "dec-1",
    }


def test_max_canonical_inline_keyboard_round_trips_callback_token() -> None:
    provider = provider_map()["max_messaging"]
    canonical = {
        "inline_keyboard": [
            [{"text": "Open", "callback_data": "menu:open"}],
            [{"text": "Site", "url": "https://example.com"}],
        ]
    }
    normalized = ProviderPayloadNormalizers().normalize_outbound(
        provider=provider,
        operation="message_send",
        payload={"user_id": "778899", "text": "choose", "reply_markup": canonical},
    )
    assert normalized["attachments"] == [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": "Open", "payload": "menu:open"}],
                    [{"type": "link", "text": "Site", "url": "https://example.com"}],
                ]
            },
        }
    ]

    from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports

    request = build_provider_vendor_transports()["max_messaging"].execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="business-a",
        operation="message_send",
        payload=normalized,
    )["request"]
    assert request["url_template"] == "https://platform-api2.max.ru/messages?user_id=778899"
    assert request["json_body"]["attachments"] == normalized["attachments"]

    callback_payload = {
        "update_type": "message_callback",
        "timestamp": 1787259600000,
        "user": {"user_id": 778899},
        "callback": {"callback_id": "max-callback-roundtrip", "payload": "menu:open"},
    }
    decoded = decode_provider_inbound(channel="max", payload=callback_payload)
    assert decoded["text"] == "menu:open"
    assert decoded["message_id"] == "max-callback-roundtrip"



def test_max_callback_identity_precedes_original_message_identity() -> None:
    callback_payload = {
        "update_type": "message_callback",
        "timestamp": 1787259600000,
        "user": {"user_id": 778899},
        "message": {
            "body": {"mid": "original-message-123", "text": "Choose"},
            "sender": {"user_id": 778899},
        },
        "callback": {"callback_id": "callback-event-456", "payload": "menu:open"},
    }
    decoded = decode_provider_inbound(channel="max", payload=callback_payload)
    assert decoded["message_id"] == "callback-event-456"
    assert decoded["user_id"] == "778899"
    assert decoded["text"] == "menu:open"

    route = ProviderWebhookRouteRegistry().extract(
        provider_map()["max_messaging"], {}, json.dumps(callback_payload).encode()
    )
    assert route["event_key"] == decoded["message_id"]
    assert route["resource_id"] == decoded["message_id"]



def test_max_keyboard_fails_closed_when_provider_row_capacity_is_exceeded() -> None:
    provider = provider_map()["max_messaging"]
    too_many = [
        {"text": f"B{index}", "callback_data": f"cmd:{index}"}
        for index in range(8)
    ]
    with pytest.raises(ValueError, match="button capacity"):
        ProviderPayloadNormalizers().normalize_outbound(
            provider=provider,
            operation="message_send",
            payload={
                "user_id": "778899",
                "text": "choose",
                "reply_markup": {"inline_keyboard": [too_many]},
            },
        )



@pytest.mark.parametrize("unsafe_time", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_provider_ingress_rejects_non_finite_timestamps_without_losing_event(unsafe_time: str) -> None:
    samples = (
        ("telegram", {
            "message": {
                "message_id": 101,
                "from": {"id": 7},
                "chat": {"id": 7},
                "text": "hello",
                "date": unsafe_time,
            }
        }, "101"),
        ("vk", {
            "type": "message_new",
            "object": {
                "message": {
                    "id": "vk-message-101",
                    "from_id": 7,
                    "peer_id": 7,
                    "text": "hello",
                    "date": unsafe_time,
                }
            },
        }, "vk-message-101"),
        ("max", {
            "update_type": "message_created",
            "timestamp": unsafe_time,
            "message": {
                "body": {"mid": "max-message-101", "text": "hello"},
                "sender": {"user_id": 7},
            },
        }, "max-message-101"),
    )
    for channel, payload, expected_id in samples:
        decoded = decode_provider_inbound(channel=channel, payload=payload)
        assert str(decoded["message_id"]) == expected_id
        assert decoded["text"] == "hello"
        assert decoded["timestamp_ms"] == 0


@pytest.mark.parametrize("actor_location", ["top_level", "callback"])
def test_max_callback_clicking_user_not_original_message_sender(actor_location: str) -> None:
    payload = {
        "update_type": "message_callback",
        "timestamp": 1787259600000,
        "message": {
            "body": {"mid": "original-bot-message", "text": "Menu"},
            "sender": {"user_id": 999999},
        },
        "callback": {"callback_id": "click-123", "payload": "menu:open"},
    }
    if actor_location == "top_level":
        payload["user"] = {"user_id": 778899}
    else:
        payload["callback"]["user"] = {"user_id": 778899}
    decoded = decode_provider_inbound(channel="max", payload=payload)
    assert decoded["user_id"] == "778899"
    assert decoded["message_id"] == "click-123"
    assert decoded["text"] == "menu:open"

    route = ProviderWebhookRouteRegistry().extract(
        provider_map()["max_messaging"], {}, json.dumps(payload).encode()
    )
    assert route["event_key"] == "click-123"
    assert route["messaging_ingress"]["user_id"] == "778899"
    assert route["messaging_ingress"]["text"] == "menu:open"


def test_vk_callback_uses_clicking_actor_not_embedded_message_sender() -> None:
    payload = {
        "type": "message_event",
        "event_id": "click-vk-42",
        "object": {
            "user_id": 770001,
            "peer_id": 200000001,
            "message": {"from_id": 990002, "id": 500, "text": "Old menu"},
            "payload": {"callback_data": "menu:open"},
        },
    }
    decoded = decode_provider_inbound(channel="vk", payload=payload)
    assert decoded["user_id"] == "770001"
    assert decoded["text"] == "menu:open"
    assert decoded["message_id"] == "click-vk-42"

    route = ProviderWebhookRouteRegistry().extract(
        provider_map()["vk_messaging"], {}, json.dumps(payload).encode()
    )
    assert route["event_key"] == "click-vk-42"
    assert route["messaging_ingress"]["user_id"] == "770001"
    assert route["messaging_ingress"]["text"] == "menu:open"
