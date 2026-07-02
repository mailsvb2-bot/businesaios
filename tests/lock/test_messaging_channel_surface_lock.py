from __future__ import annotations

from runtime.messaging.channel_types import ALL_CHANNELS


def test_messaging_channel_surface_is_multi_channel() -> None:
    required = {
        "telegram",
        "whatsapp",
        "sms",
        "email",
        "messenger",
        "instagram",
        "web_chat",
        "api",
    }

    assert required.issubset(set(ALL_CHANNELS))
