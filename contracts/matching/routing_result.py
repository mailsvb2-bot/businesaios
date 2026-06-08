from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoutingResult:
    request_id: str = ""
    decision: object = ""
    delivery_channel: str = ""
    published: bool = False
