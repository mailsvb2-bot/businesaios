from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from runtime.messaging.provider_inbound_decoder import decode_provider_inbound


@dataclass(frozen=True)
class ProviderWebhookMessagingIngress:
    channel: str
    user_id: str
    text: str
    transport_message_id: str
    correlation_id: str
    chat_id: str = ''
    external_user_ref: str = ''


def resolve_provider_webhook_messaging_ingress(*, provider: ProviderDefinition, normalized_payload: Mapping[str, Any]) -> ProviderWebhookMessagingIngress | None:
    binding = describe_provider_messaging_binding(provider)
    if binding is None:
        return None
    decoded = decode_provider_inbound(channel=binding.channel, payload=normalized_payload)
    user_id = str(decoded.get('user_id') or normalized_payload.get('session_id') or '').strip()
    chat_id = str(decoded.get('chat_id') or '').strip()
    external_user_ref = str(decoded.get('external_user_ref') or user_id or chat_id).strip()
    text = str(decoded.get('text') or normalized_payload.get('message') or '').strip()
    if not user_id or not text:
        return None
    transport_message_id = str(decoded.get('message_id') or '').strip()
    correlation_id = str(normalized_payload.get('correlation_id') or normalized_payload.get('update_id') or normalized_payload.get('event_id') or transport_message_id or user_id).strip()
    return ProviderWebhookMessagingIngress(channel=binding.channel, user_id=user_id, text=text, transport_message_id=transport_message_id, correlation_id=correlation_id, chat_id=chat_id, external_user_ref=external_user_ref)


def messaging_ingress_to_metadata(ingress: ProviderWebhookMessagingIngress | None) -> dict[str, Any]:
    if ingress is None:
        return {}
    return {'channel': ingress.channel, 'user_id': ingress.user_id, 'chat_id': ingress.chat_id, 'external_user_ref': ingress.external_user_ref, 'text': ingress.text, 'transport_message_id': ingress.transport_message_id, 'correlation_id': ingress.correlation_id}


__all__ = ['ProviderWebhookMessagingIngress', 'resolve_provider_webhook_messaging_ingress', 'messaging_ingress_to_metadata']
