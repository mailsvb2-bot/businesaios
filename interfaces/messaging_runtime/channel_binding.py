from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChannelBinding:
    channel: str
    parse_inbound: Callable[[dict], Any]
    send_outbound: Callable[[Any], Awaitable[dict]]
    render_capabilities: dict
