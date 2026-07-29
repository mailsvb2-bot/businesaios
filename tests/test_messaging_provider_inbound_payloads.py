from __future__ import annotations

import pytest

from interfaces.messaging_runtime.channel_loader import load_bindings


@pytest.mark.parametrize(
    ("channel", "payload", "expected_user", "expected_text", "expected_id"),
    [
        (
            "whatsapp",
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "contacts": [
                                        {
                                            "wa_id": "79990001122",
                                            "profile": {"name": "Anna"},
                                        }
                                    ],
                                    "messages": [
                                        {
                                            "from": "79990001122",
                                            "id": "wamid.1",
                                            "timestamp": "1710000000",
                                            "text": {"body": "Привет"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ]
            },
            "79990001122",
            "Привет",
            "wamid.1",
        ),
        (
            "slack",
            {
                "event_id": "Ev01",
                "event_time": 1710000000,
                "event": {
                    "type": "message",
                    "user": "U01",
                    "channel": "C01",
                    "text": "hello slack",
                    "ts": "1710000000.000100",
                },
            },
            "U01",
            "hello slack",
            "Ev01",
        ),
        (
            "vk",
            {
                "type": "message_new",
                "event_id": "vk-event-1",
                "object": {
                    "message": {
                        "id": 77,
                        "from_id": 42,
                        "peer_id": 42,
                        "date": 1710000000,
                        "text": "Привет VK",
                    }
                },
            },
            "42",
            "Привет VK",
            "vk-event-1",
        ),
        (
            "max",
            {
                "update_type": "message_created",
                "timestamp": 1710000000000,
                "message": {
                    "sender": {"user_id": 55, "name": "Max User"},
                    "recipient": {"chat_id": 9001},
                    "body": {"mid": "max-mid-1", "text": "Привет MAX"},
                },
            },
            "55",
            "Привет MAX",
            "max-mid-1",
        ),
        (
            "messenger",
            {
                "entry": [
                    {
                        "messaging": [
                            {
                                "sender": {"id": "fb-user-1"},
                                "timestamp": 1710000000000,
                                "message": {"mid": "fb-mid-1", "text": "Hello FB"},
                            }
                        ]
                    }
                ]
            },
            "fb-user-1",
            "Hello FB",
            "fb-mid-1",
        ),
        (
            "line",
            {
                "events": [
                    {
                        "webhookEventId": "line-event-1",
                        "timestamp": 1710000000000,
                        "source": {"type": "user", "userId": "line-user-1"},
                        "message": {"id": "line-mid-1", "type": "text", "text": "Hello LINE"},
                    }
                ]
            },
            "line-user-1",
            "Hello LINE",
            "line-mid-1",
        ),
        (
            "telegram",
            {
                "update_id": 123,
                "message": {
                    "message_id": 456,
                    "date": 1710000000,
                    "from": {"id": 789, "username": "tester"},
                    "chat": {"id": 789},
                    "text": "/start",
                },
            },
            "789",
            "/start",
            "456",
        ),
    ],
)
def test_nested_provider_payloads_reach_canonical_message_envelope(
    channel: str,
    payload: dict,
    expected_user: str,
    expected_text: str,
    expected_id: str,
) -> None:
    binding = load_bindings(enabled_channels=(channel,))[0]

    envelope = binding.parse_inbound(payload)

    assert envelope.channel == channel
    assert envelope.user_id == expected_user
    assert envelope.text == expected_text
    assert envelope.message_id == expected_id
    assert envelope.metadata["raw"] == payload
