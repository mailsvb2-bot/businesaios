from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    """Compatibility contract for older runtime-etalon tests.

    Canonical inbound runtime envelope is MessageEnvelope. This type remains as a
    minimal transport-only shim and must not grow business semantics.
    """

    channel: str
    user_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageEnvelope:
    channel: str
    user_id: str
    text: str
    message_id: str
    correlation_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.channel:
            raise ValueError("channel is required")
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.message_id:
            raise ValueError("message_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")


@dataclass(frozen=True)
class RouteCommand:
    route_key: str
    channel: str
    correlation_id: str
    message_id: str

    def validate(self) -> None:
        if not self.route_key:
            raise ValueError("route_key is required")


@dataclass(frozen=True)
class WorldStateInput:
    user_id: str
    channel: str
    correlation_id: str
    message_text: str


@dataclass(frozen=True)
class ViewModel:
    channel: str
    user_id: str
    correlation_id: str
    body: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundEnvelope:
    channel: str
    user_id: str
    correlation_id: str
    body: str
    dedupe_key: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.channel:
            raise ValueError("channel is required")
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if not self.body:
            raise ValueError("body is required")
        if not self.dedupe_key:
            raise ValueError("dedupe_key is required")
