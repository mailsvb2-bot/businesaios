from __future__ import annotations

from .contracts import InboundMessage, MessageEnvelope, RouteCommand


def route_message(message: InboundMessage | MessageEnvelope) -> str:
    channel = str(message.channel or "").strip()
    if not channel:
        raise ValueError("channel is required")
    return channel


def build_route_command(message: MessageEnvelope) -> RouteCommand:
    route = RouteCommand(
        route_key=f"channel:{route_message(message)}",
        channel=message.channel,
        correlation_id=message.correlation_id,
        message_id=message.message_id,
    )
    route.validate()
    return route
