from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.tenancy import require_tenant_id

from .inbound_message import InboundMessage
from .router_contract import ConversationRoute
from .router_extractors import (
    correlation_id_from_payload,
    external_user_ref_from_payload,
    message_id_from_payload,
    metadata_from_payload,
    text_from_payload,
    user_id_from_payload,
)


class UnifiedConversationRouter:
    """Pure runtime messaging router.

    Responsibilities:
    - normalize inbound messaging coordinates
    - derive deterministic conversation ids

    Non-responsibilities:
    - no decision-engine access
    - no policy selection
    - no action issuance
    """

    def normalize(self, *, channel: str, tenant_id: str, payload: dict) -> InboundMessage:
        normalized_channel = normalize_channel(channel)
        body = dict(payload or {})
        user_id = user_id_from_payload(body)
        transport_message_id = message_id_from_payload(body)
        return InboundMessage(
            tenant_id=require_tenant_id(tenant_id),
            channel=normalized_channel,
            user_id=user_id,
            text=text_from_payload(body),
            payload=body,
            correlation_id=correlation_id_from_payload(body, fallback_message_id=transport_message_id),
            transport_message_id=transport_message_id,
            external_user_ref=external_user_ref_from_payload(body, fallback_user_id=user_id),
            metadata=metadata_from_payload(body, channel=normalized_channel),
        )

    def route(self, message: InboundMessage) -> str:
        return self.describe(message).conversation_id

    def describe(self, message: InboundMessage) -> ConversationRoute:
        conversation_id = f"{message.channel}:{message.user_id}"
        return ConversationRoute(
            channel=message.channel,
            user_id=message.user_id,
            conversation_id=conversation_id,
        )
