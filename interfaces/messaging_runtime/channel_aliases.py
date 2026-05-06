from __future__ import annotations

CANONICAL_CHANNEL_ALIASES = {
    'web_chat': 'webchat',
    'api': 'api_gateway',
}


def canonical_channel_name(channel: str) -> str:
    key = str(channel or '').strip()
    return CANONICAL_CHANNEL_ALIASES.get(key, key)
