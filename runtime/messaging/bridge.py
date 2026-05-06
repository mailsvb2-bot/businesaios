from __future__ import annotations

from runtime.messaging.bootstrap import build_multichannel_dispatcher
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


class MultiChannelEffectsBridge:
    def __init__(self) -> None:
        self._dispatcher = build_multichannel_dispatcher()

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        return self._dispatcher.send(msg)


_BRIDGE: MultiChannelEffectsBridge | None = None


def get_multichannel_effects_bridge() -> MultiChannelEffectsBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = MultiChannelEffectsBridge()
    return _BRIDGE
