from __future__ import annotations

from runtime.messaging.adapter_protocol import MessageAdapter
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


class MultiChannelDispatcher:
    def __init__(self, *, adapters: dict[str, MessageAdapter] | None = None):
        self.adapters: dict[str, MessageAdapter] = dict(adapters or {})

    def register_adapter(self, channel: str, adapter: MessageAdapter) -> None:
        self.adapters[str(channel)] = adapter

    def send(self, message: OutboundMessage) -> DeliveryResult:
        adapter = self.adapters.get(message.channel)
        if adapter is None:
            return DeliveryResult(
                ok=False,
                channel=message.channel,
                mode="missing_adapter",
                external_id="",
                detail={"reason": "missing_adapter", "channel": message.channel},
            )
        return adapter.send(message)

    def dispatch(self, message: OutboundMessage) -> DeliveryResult:
        return self.send(message)
