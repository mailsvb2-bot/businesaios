from __future__ import annotations

from collections.abc import Callable

from .capabilities import get_capabilities
from .channel_binding import ChannelBinding
from .parsing import parse_inbound_payload


class TransportSendNotConfigured(RuntimeError):
    pass


async def _missing_sender(_outbound):
    raise TransportSendNotConfigured("transport sender is not configured")


def build_channel_binding(*, channel: str, sender: Callable | None = None) -> ChannelBinding:
    capabilities = get_capabilities(channel)

    def parse_inbound(raw: dict):
        return parse_inbound_payload(channel=channel, raw=raw)

    actual_sender = sender or _missing_sender
    return ChannelBinding(
        channel=channel,
        parse_inbound=parse_inbound,
        send_outbound=actual_sender,
        render_capabilities={
            "plain_text": capabilities.plain_text,
            "html": capabilities.html,
            "buttons": capabilities.buttons,
            "attachments": capabilities.attachments,
            "structured_payload": capabilities.structured_payload,
            "subject_line": capabilities.subject_line,
        },
    )
