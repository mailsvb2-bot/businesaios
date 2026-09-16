from __future__ import annotations

from dataclasses import dataclass

from contracts.messaging_event_identity import MessageDirection, MessageIdentity, stable_transport_message_id
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.tenancy import require_tenant_id


@dataclass(frozen=True)
class InboundMessage:
    tenant_id: str
    channel: str
    user_id: str
    text: str = ""
    payload: dict | None = None
    correlation_id: str = ""
    transport_message_id: str = ""
    external_user_ref: str = ""
    metadata: dict | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_tenant_id(self.tenant_id))
        object.__setattr__(self, "channel", normalize_channel(self.channel))
        object.__setattr__(self, "user_id", str(self.user_id or ""))
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "correlation_id", str(self.correlation_id or self.transport_message_id or ""))
        object.__setattr__(self, "transport_message_id", str(self.transport_message_id or ""))
        object.__setattr__(self, "external_user_ref", str(self.external_user_ref or self.user_id))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
    @property
    def canonical_identity(self) -> MessageIdentity:
        message_id = self.transport_message_id or self.correlation_id
        if not message_id:
            message_id = stable_transport_message_id(
                channel=self.channel,
                payload={
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id,
                    "text": self.text,
                    "payload": dict(self.payload or {}),
                },
            )
        return MessageIdentity(
            message_id=message_id,
            tenant_id=self.tenant_id,
            channel=self.channel,
            direction=MessageDirection.INBOUND,
            correlation_id=self.correlation_id,
            transport_message_id=self.transport_message_id,
        )
