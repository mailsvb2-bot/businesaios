from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from runtime.messaging.bootstrap import build_multichannel_dispatcher
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage

_NATIVE_PROVIDER_CHANNELS = frozenset({"vk", "max", "slack", "discord"})


def _bind_native_provider_context(msg: OutboundMessage) -> OutboundMessage:
    try:
        channel = normalize_channel(msg.channel)
    except ValueError:
        return msg
    if channel not in _NATIVE_PROVIDER_CHANNELS:
        return msg
    track_payload = dict(msg.track_payload or {})
    existing = track_payload.get("_provider_native")
    context = dict(existing) if isinstance(existing, Mapping) else {}
    context.setdefault("business_id", str(track_payload.get("business_id") or track_payload.get("tenant_id") or msg.tenant_id).strip())
    if track_payload.get("approval_id") and not context.get("approval_id"):
        context["approval_id"] = str(track_payload["approval_id"])
    recipient_key = {"vk": "peer_id", "max": "chat_id", "slack": "channel_id", "discord": "channel_id"}[channel]
    context.setdefault(recipient_key, str(track_payload.get(recipient_key) or msg.user_id).strip())
    track_payload["_provider_native"] = context
    return replace(msg, track_payload=track_payload)


class MultiChannelEffectsBridge:
    def __init__(self) -> None:
        self._dispatcher = build_multichannel_dispatcher()

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        return self._dispatcher.send(_bind_native_provider_context(msg))


_BRIDGE: MultiChannelEffectsBridge | None = None


def get_multichannel_effects_bridge() -> MultiChannelEffectsBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = MultiChannelEffectsBridge()
    return _BRIDGE
