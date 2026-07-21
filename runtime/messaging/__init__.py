"""Canonical runtime messaging registry.

The channel catalog now lives directly in the package namespace instead of a
standalone ``catalog.py`` module. This keeps ownership local to the package
without changing the exposed runtime behavior.
"""

from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_spec import ChannelSpec
from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state


def _spec(key: str, family: str, env_prefix: str, default_mode: str, delivery_backend: str) -> ChannelSpec:
    return ChannelSpec(key, family, env_prefix, default_mode, delivery_backend)


_CHANNELS = (
    _spec("telegram", "messaging", "TELEGRAM", "configured_noop", "bot_api"),
    _spec("whatsapp", "messaging", "WHATSAPP", "webhook", "provider_webhook"),
    _spec("sms", "messaging", "SMS", "webhook", "provider_webhook"),
    _spec("email", "messaging", "EMAIL", "smtp", "smtp"),
    _spec("instagram", "messaging", "INSTAGRAM", "webhook", "provider_webhook"),
    _spec("messenger", "messaging", "MESSENGER", "webhook", "provider_webhook"),
    _spec("slack", "collaboration", "SLACK", "webhook", "provider_webhook"),
    _spec("discord", "collaboration", "DISCORD", "webhook", "provider_webhook"),
    _spec("web_chat", "web", "WEB_CHAT", "configured_noop", "internal_widget"),
    _spec("api", "web", "API_GATEWAY", "configured_noop", "internal_api"),
    _spec("line", "regional", "LINE", "webhook", "provider_webhook"),
    _spec("wechat", "regional", "WECHAT", "webhook", "provider_webhook"),
    _spec("kakaotalk", "regional", "KAKAOTALK", "webhook", "provider_webhook"),
    _spec("viber", "regional", "VIBER", "webhook", "provider_webhook"),
)

CHANNEL_SPECS = {item.key: item for item in _CHANNELS}


def get_channel_spec(channel: str) -> ChannelSpec:
    try:
        key = normalize_channel(channel)
    except ValueError as exc:
        raw = str(channel or "").strip().lower().replace("-", "_")
        raise KeyError(f"UNKNOWN_CHANNEL:{raw}") from exc
    spec = CHANNEL_SPECS.get(key)
    if spec is None:
        raise KeyError(f"UNKNOWN_CHANNEL:{key}")
    return spec


__all__ = ["CHANNEL_SPECS", "ChannelSpec", "get_channel_spec", "map_inbound_to_world_state", "normalize_channel"]
