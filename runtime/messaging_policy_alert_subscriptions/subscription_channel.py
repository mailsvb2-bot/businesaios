from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel


def normalize_subscription_channel(value: str | None) -> str:
    return normalize_channel(value or "telegram")
