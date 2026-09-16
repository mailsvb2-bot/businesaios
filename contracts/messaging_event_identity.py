"""Stable transport-event identity shared by every messaging ingress surface."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

CANON_MESSAGING_EVENT_IDENTITY = True
CANON_MESSAGE_SEMANTIC_OWNER = True
MESSAGE_SCHEMA_VERSION = 1


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass(frozen=True, slots=True)
class MessageIdentity:
    message_id: str
    tenant_id: str
    channel: str
    direction: MessageDirection
    business_id: str = ""
    correlation_id: str = ""
    transport_message_id: str = ""
    schema_version: int = MESSAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        direction = self.direction if isinstance(self.direction, MessageDirection) else MessageDirection(str(self.direction))
        object.__setattr__(self, "message_id", str(self.message_id or "").strip())
        object.__setattr__(self, "tenant_id", str(self.tenant_id or "").strip())
        object.__setattr__(self, "business_id", str(self.business_id or "").strip())
        object.__setattr__(self, "channel", str(self.channel or "").strip().lower())
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "correlation_id", str(self.correlation_id or "").strip())
        object.__setattr__(self, "transport_message_id", str(self.transport_message_id or "").strip())
        if not self.message_id or not self.tenant_id or not self.channel:
            raise ValueError("MESSAGE_IDENTITY_SCOPE_REQUIRED")
        if self.schema_version != MESSAGE_SCHEMA_VERSION:
            raise ValueError("MESSAGE_SCHEMA_VERSION_UNSUPPORTED")


def stable_transport_message_id(*, channel: str, payload: Mapping[str, Any]) -> str:
    """Return a deterministic ID when a provider omits its own event/message ID.

    Provider-supplied IDs remain authoritative. The synthetic ID is based only on
    canonical channel identity and the original JSON payload, so retries produce
    the same dedupe key while different payloads remain distinct.
    """

    canonical_payload = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(
        f"{str(channel).strip().lower()}\n{canonical_payload}".encode()
    ).hexdigest()
    return f"synthetic-{str(channel).strip().lower()}-{digest[:32]}"


__all__ = [
    "CANON_MESSAGING_EVENT_IDENTITY",
    "CANON_MESSAGE_SEMANTIC_OWNER",
    "MESSAGE_SCHEMA_VERSION",
    "MessageDirection",
    "MessageIdentity",
    "stable_transport_message_id",
]
