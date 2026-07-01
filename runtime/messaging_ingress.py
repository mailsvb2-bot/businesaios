from __future__ import annotations

CANON_MESSAGING_INGRESS_NORMALIZATION_ONLY = True

SUPPORTED_MESSAGING_CHANNELS = (
    "telegram",
    "whatsapp",
    "vk",
    "max",
    "slack",
    "discord",
    "viber",
    "sms",
    "email",
    "webchat",
)


def normalize_messaging_channel(channel: str) -> str:
    value = str(channel or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"tg": "telegram", "wa": "whatsapp", "vkontakte": "vk", "mail": "email"}
    return aliases.get(value, value) or "unknown"


__all__ = [
    "CANON_MESSAGING_INGRESS_NORMALIZATION_ONLY",
    "SUPPORTED_MESSAGING_CHANNELS",
    "normalize_messaging_channel",
]
