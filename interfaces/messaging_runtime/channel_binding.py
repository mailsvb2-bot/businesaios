from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Awaitable, Callable


@dataclass(frozen=True)
class ChannelBinding:
    channel: str
    parse_inbound: Callable[[dict], Any]
    send_outbound: Callable[[Any], Awaitable[dict]]
    render_capabilities: dict
