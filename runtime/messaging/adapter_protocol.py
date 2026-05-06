from __future__ import annotations

from typing import Protocol

from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


class MessageAdapter(Protocol):
    def send(self, msg: OutboundMessage) -> DeliveryResult: ...
