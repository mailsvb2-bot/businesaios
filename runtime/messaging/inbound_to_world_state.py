from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging.inbound_message import InboundMessage


@dataclass(frozen=True)
class WorldStateMessageInput:
    tenant_id: str
    user_id: str
    channel: str
    message_text: str
    correlation_id: str
    transport_message_id: str


def map_inbound_to_world_state(msg: InboundMessage) -> WorldStateMessageInput:
    return WorldStateMessageInput(
        tenant_id=str(msg.tenant_id),
        user_id=str(msg.user_id),
        channel=str(msg.channel),
        message_text=str(msg.text),
        correlation_id=str(msg.correlation_id or ""),
        transport_message_id=str(msg.transport_message_id or ""),
    )
