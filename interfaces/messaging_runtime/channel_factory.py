from __future__ import annotations

from collections.abc import Callable

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.provider_inbound_decoder import decode_provider_inbound

from .capabilities import get_capabilities
from .channel_binding import ChannelBinding
from .parsing import parse_inbound_payload


class TransportSendNotConfigured(RuntimeError):
    pass


async def _missing_sender(_outbound):
    raise TransportSendNotConfigured("transport sender is not configured")


def build_channel_binding(
    *,
    channel: str,
    sender: Callable | None = None,
) -> ChannelBinding:
    channel = normalize_channel(channel)
    capabilities = get_capabilities(channel)

    def parse_inbound(raw: dict):
        normalized = decode_provider_inbound(
            channel=channel,
            payload=raw,
        )
        return parse_inbound_payload(
            channel=channel,
            raw=normalized,
        )

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


__all__ = ["TransportSendNotConfigured", "build_channel_binding"]
