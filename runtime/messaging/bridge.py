from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from runtime.messaging.bootstrap import build_multichannel_dispatcher
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage

_NATIVE_PROVIDER_CHANNELS = frozenset({"vk", "max", "slack", "discord", "instagram", "messenger", "line", "viber"})

def stamp_native_provider_provenance(msg: OutboundMessage) -> OutboundMessage:
    try:
        channel = normalize_channel(msg.channel)
    except ValueError:
        return msg
    if channel not in _NATIVE_PROVIDER_CHANNELS or not isinstance(msg.track_payload, dict):
        return msg
    existing = msg.track_payload.get("_provider_native")
    if not isinstance(existing, Mapping) or str(existing.get("provider_key") or "").strip():
        return msg
    track_payload, context = dict(msg.track_payload), dict(existing)
    context["provider_key"] = f"{channel}_messaging"
    track_payload["_provider_native"] = context
    return replace(msg, track_payload=track_payload)

def _bind_native_provider_context(msg: OutboundMessage) -> OutboundMessage:
    msg = stamp_native_provider_provenance(msg)
    try:
        channel = normalize_channel(msg.channel)
    except ValueError:
        return msg
    if channel not in _NATIVE_PROVIDER_CHANNELS:
        return msg
    existing = (track_payload := dict(msg.track_payload or {})).get("_provider_native")
    context = dict(existing) if isinstance(existing, Mapping) else {}
    provider_key = f"{channel}_messaging"
    provider_changed = bool((source_provider := str(context.get("provider_key") or "").strip()) and source_provider != provider_key)
    if provider_changed:
        for key in ("peer_id", "chat_id", "random_id", "channel_id", "recipient_id", "to", "receiver", "approval_id"):
            context.pop(key, None)
    context["provider_key"] = provider_key
    business_id = str(context.get("business_id") or msg.business_id or track_payload.get("business_id") or "").strip()
    if msg.business_id and business_id and msg.business_id != business_id:
        raise RuntimeError("BUSINESS_SCOPE_MISMATCH")
    if business_id:
        context["business_id"] = business_id
    if track_payload.get("approval_id") and not context.get("approval_id") and not provider_changed:
        context["approval_id"] = str(track_payload["approval_id"])
    recipient_key = {"vk": "peer_id", "max": "chat_id", "slack": "channel_id", "discord": "channel_id", "instagram": "recipient_id", "messenger": "recipient_id", "line": "to", "viber": "receiver"}[channel]
    recipient = str(msg.user_id if provider_changed else (track_payload.get(recipient_key) or msg.user_id)).strip()
    context.setdefault(recipient_key, recipient)
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
